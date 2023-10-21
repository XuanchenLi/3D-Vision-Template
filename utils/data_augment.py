"""
Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V. (MPG) is
holder of all proprietary rights on this computer program.
Using this computer program means that you agree to the terms 
in the LICENSE file included with this software distribution. 
Any use not explicitly granted by the LICENSE is prohibited.

Copyright©2023 Max-Planck-Gesellschaft zur Förderung
der Wissenschaften e.V. (MPG). acting on behalf of its Max Planck Institute
for Intelligent Systems. All rights reserved.

For comments or questions, please email us at tempeh@tue.mpg.de
"""

import os
import random
import imageio
import numpy as np

# -----------------------------------------------------------------------------

def get_subset_views(number_views, minimum_views=4):       
    views = np.arange(number_views)
    if minimum_views >= number_views:
        return views

    random.shuffle(views)
    number_selected_views = int(round(minimum_views + (number_views - minimum_views) * np.random.random(), 0))
    return views[:number_selected_views]

# -----------------------------------------------------------------------------

def get_random_crop_offsets(crop_size, height, width):
    if isinstance(crop_size, tuple):
        crop_height = crop_size[0]
        crop_width = crop_size[1]
    else:
        crop_width = crop_height = crop_size

    w_offset = np.random.randint(0, max(1, width - crop_width - 1))
    h_offset = np.random.randint(0, max(1, height - crop_height - 1))
    return h_offset, w_offset

# -----------------------------------------------------------------------------

def pad_width_or_height( data, output_width=256, output_height=256, pad_value=0, return_offsets=False ):
    # pad the image to be at least (output_height, output_width) resolution
    # assume data in shape (h,w,*)
    from PIL import Image
    if isinstance( data, np.ndarray ):
        height, width = data.shape[0], data.shape[1]
        with_channel = len(data.shape) == 3
    elif isinstance( data, Image.Image ):
        height, width = data.height, data.width
        with_channel = len(data.size) == 3

    p_left, p_right, p_top, p_bottom = 0, 0, 0, 0
    if width < output_width:
        p_left  = int( np.floor( ( output_width - width ) / 2 ) )
        p_right = ( output_width - width ) - p_left
    if height < output_height:
        p_top = int( np.floor( ( output_height - height ) / 2 ) )
        p_bottom = ( output_height - height ) - p_top

    if isinstance( data, np.ndarray ):
        if with_channel:
            data = np.pad( data, ( (p_top,p_bottom), (p_left,p_right), (0,0) ), 'constant', constant_values=pad_value )
        else:
            data = np.pad( data, ( (p_top,p_bottom), (p_left,p_right) ), 'constant', constant_values=pad_value )
    elif isinstance( data, Image.Image ):
        import torchvision.transforms as transforms
        data = transforms.Pad( (p_left, p_top, p_right, p_bottom) )( data ) # ( left, top, right, bottom )

    if return_offsets:
        return data, p_top, p_bottom, p_left, p_right
    else:
        return data

# # -----------------------------------------------------------------------------

def crop_img(img, crop_size, h_offset, w_offset):
    '''crop an image
    Args:
        img: np.array or tensor image in shape (H,W,C)
        crop_size: tuple (crop_h, crop_w) or scale (assuming square crop)
        h_offset, w_offset: scalars generated by get_random_crop_offsets()
    Returns:
        cropped image
    '''
    if isinstance(img, np.ndarray):
        dim = img.ndim
    elif torch.is_tensor(img):
        dim = img.ndimension() # instead of img.ndim, pytorch 1.1 compatibility issue 
    else:
        raise RuntimeError(f"invalid image type = {type(img)}")

    if isinstance(crop_size, tuple):
        crop_height = crop_size[0]
        crop_width = crop_size[1]
    else:
        crop_width = crop_height = crop_size

    if dim == 3:
        return img[h_offset: h_offset+crop_height,
                   w_offset: w_offset+crop_width, :]
    elif dim == 2:
        return img[h_offset: h_offset+crop_height,
                   w_offset: w_offset+crop_width]

# -----------------------------------------------------------------------------

def scale_crop(img, crop_size, h_offset, w_offset, scale_factor, K=None, debug=False, debug_root=None):
    '''apply (1) scale and (2) crop (with optionally padding)
    Args:
        img: np.array image in shape (H,W,C)
        crop_size: tuple (crop_h, crop_w) or scale (assuming square crop)
        h_offset, w_offset: scalars generated by get_crop_offsets()
        scale_factor: scalar, if > 1.0, then enlarge, else shrink
        K (optional): intrinsic matrix in np.array (3,3)
    Returns:
        img_aug: result image, should always be in crop_size
        K_aug (if K provided): result intrinsic
    '''
    from skimage.transform import rescale, resize
    if isinstance(img, np.ndarray):
        dim = img.ndim
    else:
        raise RuntimeError(f"invalid image type = {type(img)}")

    if isinstance(crop_size, tuple):
        crop_height = crop_size[0]
        crop_width = crop_size[1]
    else:
        crop_width = crop_height = crop_size

    # debug
    if debug:
        if debug_root is None:
            debug_root = '/home/ICT2000/tli/Dropbox/DenseFaceTracking/debug/image_perturbation_with_intrinsics'
        imageio.imsave(os.path.join(debug_root, '0_input.png'), (255.*img).astype(np.uint8))

    # scaling
    if dim == 3:
        # img = rescale( img.copy(), scale_factor, multichannel=True, anti_aliasing=True )
        img = rescale( img.copy(), scale_factor, channel_axis=2, anti_aliasing=True )
    elif dim == 2:
        # img = rescale( img.copy(), scale_factor, multichannel=False, anti_aliasing=True )
        img = rescale( img.copy(), scale_factor, anti_aliasing=True )
    else:
        raise RuntimeError(f"invalid input image dimension num = {dim}")
    if debug: imageio.imsave(os.path.join(debug_root, '1_scaled.png'), (255.*img).astype(np.uint8))

    # crop
    img = crop_img(img, crop_size, h_offset, w_offset)
    if debug: imageio.imsave(os.path.join(debug_root, '2_cropped.png'), (255.*img).astype(np.uint8))

    # pad
    if img.shape[0] < crop_height or img.shape[1] < crop_width:
        img, p_top, p_bottom, p_left, p_right = pad_width_or_height(
            img, output_width=crop_width, output_height=crop_height, return_offsets=True) # pad to at least bigger than target size
    else:
        p_top, p_bottom, p_left, p_right = 0., 0., 0., 0.
    if debug: imageio.imsave(os.path.join(debug_root, '3_padded.png'), (255.*img).astype(np.uint8))

    # adjust intrinsic, if provided
    if K is not None:
        Ks = np.eye(3); Ks[0,0] = scale_factor; Ks[1,1] = scale_factor
        Kc = np.eye(3); Kc[0,2] = -1.0 * float(w_offset); Kc[1,2] = -1.0 * float(h_offset)
        Kp = np.eye(3); Kp[0,2] = float(p_left); Kp[1,2] = float(p_top)
        K_aug = Kp.dot( Kc.dot( Ks.dot(K.copy()) ) )
        return img, K_aug
    else:
        return img
