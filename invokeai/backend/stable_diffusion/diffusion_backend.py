from __future__ import annotations

import torch
from diffusers.models.unets.unet_2d_condition import UNet2DConditionModel
from diffusers.schedulers.scheduling_utils import SchedulerMixin, SchedulerOutput
from tqdm.auto import tqdm

from invokeai.app.services.config.config_default import get_config
from invokeai.backend.stable_diffusion.denoise_context import DenoiseContext, UNetKwargs
from invokeai.backend.stable_diffusion.extensions_manager import ExtensionsManager


class StableDiffusionBackend:
    def __init__(
        self,
        unet: UNet2DConditionModel,
        scheduler: SchedulerMixin,
    ):
        self.unet = unet
        self.scheduler = scheduler
        config = get_config()
        self.sequential_guidance = config.sequential_guidance

    def latents_from_embeddings(self, ctx: DenoiseContext, ext_manager: ExtensionsManager):
        if ctx.init_timestep.shape[0] == 0:
            return ctx.latents

        ctx.orig_latents = ctx.latents.clone()

        if ctx.noise is not None:
            batch_size = ctx.latents.shape[0]
            # latents = noise * self.scheduler.init_noise_sigma # it's like in t2l according to diffusers
            ctx.latents = ctx.scheduler.add_noise(ctx.latents, ctx.noise, ctx.init_timestep.expand(batch_size))

        # if no work to do, return latents
        if ctx.timesteps.shape[0] == 0:
            return ctx.latents

        # ext: inpaint[pre_denoise_loop, priority=normal] (maybe init, but not sure if it needed)
        # ext: preview[pre_denoise_loop, priority=low]
        ext_manager.callbacks.pre_denoise_loop(ctx, ext_manager)

        for ctx.step_index, ctx.timestep in enumerate(tqdm(ctx.timesteps)):  # noqa: B020
            # ext: inpaint (apply mask to latents on non-inpaint models)
            ext_manager.callbacks.pre_step(ctx, ext_manager)

            # ext: tiles? [override: step]
            ctx.step_output = self.step(ctx, ext_manager)

            # ext: inpaint[post_step, priority=high] (apply mask to preview on non-inpaint models)
            # ext: preview[post_step, priority=low]
            ext_manager.callbacks.post_step(ctx, ext_manager)

            ctx.latents = ctx.step_output.prev_sample

        # ext: inpaint[post_denoise_loop] (restore unmasked part)
        ext_manager.callbacks.post_denoise_loop(ctx, ext_manager)
        return ctx.latents

    @torch.inference_mode()
    def step(self, ctx: DenoiseContext, ext_manager: ExtensionsManager) -> SchedulerOutput:
        ctx.latent_model_input = ctx.scheduler.scale_model_input(ctx.latents, ctx.timestep)

        # TODO: conditionings as list(conditioning_data.to_unet_kwargs - ready)
        # Note: The current handling of conditioning doesn't feel very future-proof.
        # This might change in the future as new requirements come up, but for now,
        # this is the rough plan.
        if self.sequential_guidance:
            ctx.negative_noise_pred = self.run_unet(ctx, ext_manager, "negative")
            ctx.positive_noise_pred = self.run_unet(ctx, ext_manager, "positive")
        else:
            both_noise_pred = self.run_unet(ctx, ext_manager, "both")
            ctx.negative_noise_pred, ctx.positive_noise_pred = both_noise_pred.chunk(2)

        # ext: override apply_cfg
        ctx.noise_pred = self.apply_cfg(ctx)

        # ext: cfg_rescale [modify_noise_prediction]
        # TODO: rename
        ext_manager.callbacks.post_apply_cfg(ctx, ext_manager)

        # compute the previous noisy sample x_t -> x_t-1
        step_output = ctx.scheduler.step(ctx.noise_pred, ctx.timestep, ctx.latents, **ctx.scheduler_step_kwargs)

        # del locals
        del ctx.latent_model_input
        del ctx.negative_noise_pred
        del ctx.positive_noise_pred
        del ctx.noise_pred

        return step_output

    @staticmethod
    def apply_cfg(ctx: DenoiseContext) -> torch.Tensor:
        guidance_scale = ctx.conditioning_data.guidance_scale
        if isinstance(guidance_scale, list):
            guidance_scale = guidance_scale[ctx.step_index]

        return torch.lerp(ctx.negative_noise_pred, ctx.positive_noise_pred, guidance_scale)
        # return ctx.negative_noise_pred + guidance_scale * (ctx.positive_noise_pred - ctx.negative_noise_pred)

    def run_unet(self, ctx: DenoiseContext, ext_manager: ExtensionsManager, conditioning_mode: str):
        sample = ctx.latent_model_input
        if conditioning_mode == "both":
            sample = torch.cat([sample] * 2)

        ctx.unet_kwargs = UNetKwargs(
            sample=sample,
            timestep=ctx.timestep,
            encoder_hidden_states=None,  # set later by conditoning
            cross_attention_kwargs=dict(  # noqa: C408
                percent_through=ctx.step_index / len(ctx.timesteps),  # ctx.total_steps,
            ),
        )

        ctx.conditioning_mode = conditioning_mode
        ctx.conditioning_data.to_unet_kwargs(ctx.unet_kwargs, ctx.conditioning_mode)

        # ext: controlnet/ip/t2i [pre_unet]
        ext_manager.callbacks.pre_unet(ctx, ext_manager)

        # ext: inpaint [pre_unet, priority=low]
        # or
        # ext: inpaint [override: unet_forward]
        noise_pred = self._unet_forward(**vars(ctx.unet_kwargs))

        ext_manager.callbacks.post_unet(ctx, ext_manager)

        del ctx.unet_kwargs
        del ctx.conditioning_mode

        return noise_pred

    def _unet_forward(self, **kwargs) -> torch.Tensor:
        return self.unet(**kwargs).sample
