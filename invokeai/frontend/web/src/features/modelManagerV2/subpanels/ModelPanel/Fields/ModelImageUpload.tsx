import { Box, IconButton, Image } from '@invoke-ai/ui-library';
import { typedMemo } from 'common/util/typedMemo';
import { useCallback, useEffect, useMemo } from 'react';
import type { UseControllerProps } from 'react-hook-form';
import { useController, useWatch } from 'react-hook-form';
import type { AnyModelConfig } from 'services/api/types';

import { Button } from '@invoke-ai/ui-library';
import { useDropzone } from 'react-dropzone';
import { PiArrowCounterClockwiseBold, PiUploadSimpleBold } from 'react-icons/pi';
import { useGetModelImageQuery } from 'services/api/endpoints/models';

const ModelImageUpload = (props: UseControllerProps<AnyModelConfig>) => {
  const { field } = useController(props);

  const key = useWatch({ control: props.control, name: 'key' });

  const { data } = useGetModelImageQuery(key);

  const onDropAccepted = useCallback(
    (files: File[]) => {
      const file = files[0];

      if (!file) {
        return;
      }

      field.onChange(file);
    },
    [field]
  );

  const handleResetControlImage = useCallback(() => {
    field.onChange(undefined);
  }, [field]);

  const { getInputProps, getRootProps } = useDropzone({
    accept: { 'image/png': ['.png'], 'image/jpeg': ['.jpg', '.jpeg', '.png'] },
    onDropAccepted,
    noDrag: true,
    multiple: false,
  });

  const image = useMemo(() => {
    console.log(field.value, 'asdf' );
    if (field.value) {
      return URL.createObjectURL(field.value);
    }

    return data;
  }, [field.value, data]);

  if (image) {
    return (
      <Box>
        <Image
          src={image}
          objectFit="contain"
          maxW="full"
          maxH="200px"
          borderRadius="base"
        />
        <IconButton
          onClick={handleResetControlImage}
          aria-label="reset this image"
          tooltip="reset this image"
          icon={<PiArrowCounterClockwiseBold size={16} />}
          size="sm"
          variant="link"
        />
      </Box>
    );
  }

  return (
    <>
      <Button leftIcon={<PiUploadSimpleBold />} {...getRootProps()} pointerEvents="auto">
        Upload Image
      </Button>
      <input {...getInputProps()} />
    </>
  );
};

export default typedMemo(ModelImageUpload);