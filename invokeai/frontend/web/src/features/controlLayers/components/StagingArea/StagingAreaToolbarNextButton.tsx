import { IconButton } from '@invoke-ai/ui-library';
import { useStore } from '@nanostores/react';
import { useAppDispatch, useAppSelector } from 'app/store/storeHooks';
import { INTERACTION_SCOPES } from 'common/hooks/interactionScopes';
import { useCanvasManager } from 'features/controlLayers/contexts/CanvasManagerProviderGate';
import {
  selectImageCount,
  stagingAreaNextStagedImageSelected,
} from 'features/controlLayers/store/canvasStagingAreaSlice';
import { memo, useCallback } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import { useTranslation } from 'react-i18next';
import { PiArrowRightBold } from 'react-icons/pi';

export const StagingAreaToolbarNextButton = memo(() => {
  const dispatch = useAppDispatch();
  const canvasManager = useCanvasManager();
  const imageCount = useAppSelector(selectImageCount);
  const shouldShowStagedImage = useStore(canvasManager.stagingArea.$shouldShowStagedImage);
  const isCanvasActive = useStore(INTERACTION_SCOPES.canvas.$isActive);

  const { t } = useTranslation();

  const selectNext = useCallback(() => {
    dispatch(stagingAreaNextStagedImageSelected());
  }, [dispatch]);

  useHotkeys(
    ['right'],
    selectNext,
    {
      preventDefault: true,
      enabled: isCanvasActive && shouldShowStagedImage && imageCount > 1,
    },
    [isCanvasActive, shouldShowStagedImage, imageCount]
  );

  return (
    <IconButton
      tooltip={`${t('controlLayers.stagingArea.next')} (Right)`}
      aria-label={`${t('controlLayers.stagingArea.next')} (Right)`}
      icon={<PiArrowRightBold />}
      onClick={selectNext}
      colorScheme="invokeBlue"
      isDisabled={imageCount <= 1 || !shouldShowStagedImage}
    />
  );
});

StagingAreaToolbarNextButton.displayName = 'StagingAreaToolbarNextButton';
