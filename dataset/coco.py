import os
import os.path as osp
import cv2
import numpy as np
from dataset.pycocotools.coco import COCO
from dataset import transform
import tensorflow as tf
from base import COCO_LABEL,COCO_ANCHOR
tf.config.gpu.set_per_process_memory_growth(True)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


class COCOdataset(object):
  def __init__(self, dataset_root,transform,subset,shuffle):
    self.dataset_root = dataset_root
    self.image_dir = "{}/images/{}2017".format(dataset_root, subset)
    self.coco = COCO("{}/annotations/instances_{}2017.json".format(dataset_root, subset))
    self.anchors = np.array(COCO_ANCHOR)
    self.shuffle=shuffle
    # get the mapping from original category ids to labels
    self.cat_ids = self.coco.getCatIds()
    self.cat2label = {
      cat_id: i
      for i, cat_id in enumerate(self.cat_ids)
    }
    self.img_ids, self.img_infos = self._filter_imgs()
    self._transform=transform
  def _filter_imgs(self, min_size=32):
    '''Filter images too small or without ground truths.

    Args
    ---
        min_size: the minimal size of the image.
    '''
    # Filter images without ground truths.
    all_img_ids = list(set([_['image_id'] for _ in self.coco.anns.values()]))
    # Filter images too small.
    img_ids = []
    img_infos = []
    for i in all_img_ids:
      info = self.coco.loadImgs(i)[0]
      ann_ids = self.coco.getAnnIds(imgIds=i)
      ann_info = self.coco.loadAnns(ann_ids)
      ann = self._parse_ann_info(ann_info)
      if min(info['width'], info['height']) >= min_size and ann['labels'].shape[0] != 0:
        img_ids.append(i)
        img_infos.append(info)
    return img_ids, img_infos

  def _load_ann_info(self, idx):
    img_id = self.img_ids[idx]
    ann_ids = self.coco.getAnnIds(imgIds=img_id)
    ann_info = self.coco.loadAnns(ann_ids)
    return ann_info

  def _parse_ann_info(self, ann_info):
    '''Parse bbox annotation.

    Args
    ---
        ann_info (list[dict]): Annotation info of an image.

    Returns
    ---
        dict: A dict containing the following keys: bboxes,
            bboxes_ignore, labels.
    '''
    gt_bboxes = []
    gt_labels = []
    gt_bboxes_ignore = []

    for i, ann in enumerate(ann_info):
      if ann.get('ignore', False):
        continue
      x1, y1, w, h = ann['bbox']
      if ann['area'] <= 0 or w < 1 or h < 1:
        continue
      bbox = [x1,y1,x1+w,y1+h]
      if ann['iscrowd']:
        gt_bboxes_ignore.append(bbox)
      else:
        gt_bboxes.append(bbox)
        gt_labels.append(self.cat2label[ann['category_id']])

    if gt_bboxes:
      gt_bboxes = np.array(gt_bboxes, dtype=np.float32)
      gt_labels = np.array(gt_labels, dtype=np.int64)
    else:
      gt_bboxes = np.zeros((0, 4), dtype=np.float32)
      gt_labels = np.array([], dtype=np.int64)

    if gt_bboxes_ignore:
      gt_bboxes_ignore = np.array(gt_bboxes_ignore, dtype=np.float32)
    else:
      gt_bboxes_ignore = np.zeros((0, 4), dtype=np.float32)

    ann = dict(bboxes=gt_bboxes, labels=gt_labels, bboxes_ignore=gt_bboxes_ignore)

    return ann

  def __len__(self):
    return len(self.img_infos)

  def __call__(self):
    indices = np.arange(len(self.img_infos))
    if self.shuffle:
      np.random.shuffle(indices)
    for idx in indices:
      img_info = self.img_infos[idx]
      ann_info = self._load_ann_info(idx)
      # load the image.
      img = cv2.imread(osp.join(self.image_dir, img_info['file_name']), cv2.IMREAD_COLOR)
      img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
      ori_shape = img.shape[:2]

      # Load the annotation.
      ann = self._parse_ann_info(ann_info)
      bboxes = ann['bboxes'] #[x1,y1,x2,y2]
      labels = ann['labels']
      img,bboxes=self._transform(416,416,img,bboxes)

      list_grids = transform.preprocess(bboxes, labels, img.shape[:2], class_num=80, anchors=self.anchors)

      pad_scale=(1,1)
      yield img.astype(np.float32), \
             osp.join(self.image_dir, img_info['file_name']), \
             osp.join(self.image_dir, img_info['file_name']), \
             np.array(pad_scale).astype(np.float32), \
             np.array(ori_shape).astype(np.float32), \
             list_grids[0].astype(np.float32), \
             list_grids[1].astype(np.float32), \
             list_grids[2].astype(np.float32),


def cluster(dataset_root,k=9,):
  datatransform = transform.YOLO3DefaultValTransform(mean=(0, 0, 0), std=(1, 1, 1))
  trainset = COCOdataset(dataset_root, datatransform, subset='train', shuffle=False)
  for idx in range(len(trainset)):
    print(trainset.img_ids[idx])
    ann_info=trainset._load_ann_info(idx)
    ann = trainset._parse_ann_info(ann_info)
    print(ann['bboxes'])
    assert 0
def get_dataset(dataset_root,batch_size):
  datatransform = transform.YOLO3DefaultValTransform(mean=(0,0,0),std=(1,1,1))
  valset = COCOdataset(dataset_root,datatransform,subset='val',shuffle=False)
  valset = tf.data.Dataset.from_generator(valset,
                                          ((tf.float32, tf.string,tf.string, tf.float32, tf.float32, tf.float32, tf.float32,
                                            tf.float32)))
  valset = valset.batch(batch_size).prefetch(tf.data.experimental.AUTOTUNE)
  datatransform = transform.YOLO3DefaultTrainTransform(mean=(0,0,0),std=(1,1,1))
  trainset = COCOdataset(dataset_root,datatransform,subset='train',shuffle=True)
  trainset = tf.data.Dataset.from_generator(trainset,
                                            ((tf.float32, tf.string, tf.float32, tf.float32, tf.float32, tf.float32,
                                              tf.float32)))
  #be careful to drop the last smaller batch if using tf.function
  trainset = trainset.batch(batch_size,drop_remainder=True).prefetch(tf.data.experimental.AUTOTUNE)

  return trainset, valset


if __name__ == '__main__':
  import json
  import matplotlib.pyplot as plt
  cluster('/home/gwl/datasets/coco2017',9)
  # train, val = get_dataset('/home/gwl/datasets/coco2017',8)
  # for i, inputs in enumerate(val):
  #   img = inputs[0][0].numpy()
  #   print(inputs[0][-2].shape)
  #   plt.imshow(img / img.max())
  #   plt.show()
  #   assert 0
