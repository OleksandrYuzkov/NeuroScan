Датасет: https://www.kaggle.com/datasets/masoudnickparvar/brain-tumor-mri-dataset/data

Розпакуйте дані в папку `data/brain_mri` у такій структурі:

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

Назви папок використовуються як імена класів моделі:

- `glioma`
- `meningioma`
- `pituitary`
- `no_tumor`

Після підготовки даних запустіть `notebooks/train_and_visualize.ipynb`.
