Dataset: https://www.kaggle.com/datasets/masoudnickparvar/brain-tumor-mri-dataset/data

Extract the data into the `data/brain_mri` folder with the following structure:

```text
data/
  brain_mri/
    Training/
      glioma/
      meningioma/
      pituitary/
      no_tumor/
    Testing/
      glioma/
      meningioma/
      pituitary/
      no_tumor/
```

Folder names are used as model class names:

- `glioma`
- `meningioma`
- `pituitary`
- `no_tumor`

After preparing the data, run `notebooks/train_and_visualize.ipynb`.
