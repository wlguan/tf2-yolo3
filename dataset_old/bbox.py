import cv2
import numpy as np
import random
def bbox_iou(bbox_a, bbox_b, offset=0):
  """Calculate Intersection-Over-Union(IOU) of two bounding boxes.

  Parameters
  ----------
  bbox_a : numpy.ndarray
      An ndarray with shape :math:`(N, 4)`.
  bbox_b : numpy.ndarray
      An ndarray with shape :math:`(M, 4)`.
  offset : float or int, default is 0
      The ``offset`` is used to control the whether the width(or height) is computed as
      (right - left + ``offset``).
      Note that the offset must be 0 for normalized bboxes, whose ranges are in ``[0, 1]``.

  Returns
  -------
  numpy.ndarray
      An ndarray with shape :math:`(N, M)` indicates IOU between each pairs of
      bounding boxes in `bbox_a` and `bbox_b`.

  """
  if bbox_a.shape[1] < 4 or bbox_b.shape[1] < 4:
    raise IndexError("Bounding boxes axis 1 must have at least length 4")

  tl = np.maximum(bbox_a[:, None, :2], bbox_b[:, :2])
  br = np.minimum(bbox_a[:, None, 2:4], bbox_b[:, 2:4])

  area_i = np.prod(br - tl + offset, axis=2) * (tl < br).all(axis=2)
  area_a = np.prod(bbox_a[:, 2:4] - bbox_a[:, :2] + offset, axis=1)
  area_b = np.prod(bbox_b[:, 2:4] - bbox_b[:, :2] + offset, axis=1)
  return area_i / (area_a[:, None] + area_b - area_i)

def bbox_crop(bbox, crop_box=None, allow_outside_center=True):
  """Crop bounding boxes according to slice area.

  This method is mainly used with image cropping to ensure bonding boxes fit
  within the cropped image.

  Parameters
  ----------
  bbox : numpy.ndarray
      Numpy.ndarray with shape (N, 4+) where N is the number of bounding boxes.
      The second axis represents attributes of the bounding box.
      Specifically, these are :math:`(x_{min}, y_{min}, x_{max}, y_{max})`,
      we allow additional attributes other than coordinates, which stay intact
      during bounding box transformations.
  crop_box : tuple
      Tuple of length 4. :math:`(x_{min}, y_{min}, width, height)`
  allow_outside_center : bool
      If `False`, remove bounding boxes which have centers outside cropping area.

  Returns
  -------
  numpy.ndarray
      Cropped bounding boxes with shape (M, 4+) where M <= N.
  """
  bbox = bbox.copy()
  if crop_box is None:
    return bbox
  if not len(crop_box) == 4:
    raise ValueError(
      "Invalid crop_box parameter, requires length 4, given {}".format(str(crop_box)))
  if sum([int(c is None) for c in crop_box]) == 4:
    return bbox

  l, t, w, h = crop_box

  left = l if l else 0
  top = t if t else 0
  right = left + (w if w else np.inf)
  bottom = top + (h if h else np.inf)
  crop_bbox = np.array((left, top, right, bottom))

  if allow_outside_center:
    mask = np.ones(bbox.shape[0], dtype=bool)
  else:
    centers = (bbox[:, :2] + bbox[:, 2:4]) / 2
    mask = np.logical_and(crop_bbox[:2] <= centers, centers < crop_bbox[2:]).all(axis=1)
    #satisfy both x and y
  # transform borders
  bbox[:, :2] = np.maximum(bbox[:, :2], crop_bbox[:2])
  bbox[:, 2:4] = np.minimum(bbox[:, 2:4], crop_bbox[2:4])
  bbox[:, :2] -= crop_bbox[:2]
  bbox[:, 2:4] -= crop_bbox[:2]

  mask = np.logical_and(mask, (bbox[:, :2] < bbox[:, 2:4]).all(axis=1))
  bbox = bbox[mask]
  return bbox

def bbox_resize(bbox, in_size, out_size):
  """Resize bouding boxes according to image resize operation.

  Parameters
  ----------
  bbox : numpy.ndarray
      Numpy.ndarray with shape (N, 4+) where N is the number of bounding boxes.
      The second axis represents attributes of the bounding box.
      Specifically, these are :math:`(x_{min}, y_{min}, x_{max}, y_{max})`,
      we allow additional attributes other than coordinates, which stay intact
      during bounding box transformations.
  in_size : tuple
      Tuple of length 2: (width, height) for input.
  out_size : tuple
      Tuple of length 2: (width, height) for output.

  Returns
  -------
  numpy.ndarray
      Resized bounding boxes with original shape.
  """
  if not len(in_size) == 2:
    raise ValueError("in_size requires length 2 tuple, given {}".format(len(in_size)))
  if not len(out_size) == 2:
    raise ValueError("out_size requires length 2 tuple, given {}".format(len(out_size)))

  bbox = bbox.copy()
  x_scale = out_size[0] / in_size[0]
  y_scale = out_size[1] / in_size[1]
  bbox[:, 1] = y_scale * bbox[:, 1]
  bbox[:, 3] = y_scale * bbox[:, 3]
  bbox[:, 0] = x_scale * bbox[:, 0]
  bbox[:, 2] = x_scale * bbox[:, 2]
  return bbox

def bbox_flip(bboxes, img_shape):
  '''Flip bboxes horizontally.

  Args
  ---
      bboxes: [..., 4]
      img_shape: Tuple. (height, width)

  Returns
  ---
      np.ndarray: the flipped bboxes.
  '''
  w = img_shape[1]
  flipped = bboxes.copy()
  flipped[..., 1] = w - bboxes[..., 3] - 1
  flipped[..., 3] = w - bboxes[..., 1] - 1
  return flipped

def translate(bbox, x_offset=0, y_offset=0):
  """Translate bounding boxes by offsets.

  Parameters
  ----------
  bbox : numpy.ndarray
      Numpy.ndarray with shape (N, 4+) where N is the number of bounding boxes.
      The second axis represents attributes of the bounding box.
      Specifically, these are :math:`(x_{min}, y_{min}, x_{max}, y_{max})`,
      we allow additional attributes other than coordinates, which stay intact
      during bounding box transformations.
  x_offset : int or float
      Offset along x axis.
  y_offset : int or float
      Offset along y axis.

  Returns
  -------
  numpy.ndarray
      Translated bounding boxes with original shape.
  """
  bbox = bbox.copy()
  bbox[:, :2] += (x_offset, y_offset)
  bbox[:, 2:4] += (x_offset, y_offset)
  return bbox
