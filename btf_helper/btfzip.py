from collections import Counter
from sys import stderr
from typing import Tuple
from zipfile import ZipFile

import cv2
import numpy as np

AnglesTuple = Tuple[float, float, float, float]


class Btfzip:
    """画像ファイルを格納したzipファイルから角度と画像を取り出す（小数点角度と画像形式対応）

    角度は全て度数法(degree)を用いている。
    zipファイルに含まれる角度情報の順番は保証せず、並べ替えもしない。
    `angles_set`には`list`ではなく、順序の無い`set`を用いている。

    画像の実体はopencvと互換性のあるndarray形式(BGR, channels-last)で出力する。

    zipファイル要件:
        "tl{float}{angle_sep}pl{float}{angle_sep}tv{float}{angle_sep}pv{float}.{file_ext}"
        を格納している。
        例) "tl20.25_pl10_tv11.5_pv0.exr"

    Attributes:
        zip_filepath (str): コンストラクタに指定したzipファイルパス。
        angles_set (set[tuple[float,float,float,float]]):
            zipファイルに含まれる画像の角度条件の集合。

    Example:
        >>> btf = ExrInZip("Colorchecker.zip")
        >>> angles_list = list(btf.angles_set)
        >>> image = btf.angles_to_image(*angles_list[0])
        >>> print(image.shape)
        (256, 256, 3)
        >>> print(angles_list[0])
        (0, 0, 0, 0)
    """

    def __init__(
        self, zip_filepath: str, file_ext: str = ".exr", angle_sep: str = " "
    ) -> None:
        """使用するzipファイルを指定する

        指定したzipファイルに角度条件の重複がある場合、
        何が重複しているか表示し、`RuntimeError`を投げる。
        """
        self.zip_filepath = zip_filepath
        self.__z = ZipFile(zip_filepath)

        # ファイルパスは重複しないので`filepath_set`はsetで良い
        filepath_set = {path for path in self.__z.namelist() if path.endswith(file_ext)}
        self.__angles_vs_filepath_dict = {
            self._filename_to_angles(path, angle_sep): path for path in filepath_set
        }
        self.angles_set = frozenset(self.__angles_vs_filepath_dict.keys())

        # 角度条件の重複がある場合、何が重複しているか調べる
        if len(filepath_set) != len(self.angles_set):
            angles_list = [self._filename_to_angles(path) for path in filepath_set]
            angle_collection = Counter(angles_list)
            for angles, counter in angle_collection.items():
                if counter > 1:
                    print(
                        f"[BTF-Helper] '{self.zip_filepath}' has"
                        + f"{counter} files with condition {angles}.",
                        file=stderr,
                    )
            raise RuntimeError(f"'{self.zip_filepath}' has duplicated conditions.")

    @staticmethod
    def _filename_to_angles(filename: str, sep: str) -> AnglesTuple:
        """ファイル名(orパス)から角度(`int`)のタプル(`tl`, `pl`, `tv`, `pv`)を取得する"""
        angles = filename.split("/")[-1][:-4].split(sep)
        try:
            tl = float(angles[0][2:])
            pl = float(angles[1][2:])
            tv = float(angles[2][2:])
            pv = float(angles[3][2:])
        except ValueError as e:
            raise ValueError("invalid angle:", angles) from e
        return (tl, pl, tv, pv)

    def angles_to_image(self, tl: int, pl: int, tv: int, pv: int) -> np.ndarray:
        """`tl`, `pl`, `tv`, `pv`の角度条件の画像をndarray形式で返す

        `filename`が含まれるファイルが存在しない場合は`ValueError`を投げる。
        """
        key = (tl, pl, tv, pv)
        filepath = self.__angles_vs_filepath_dict.get(key)
        if not filepath:
            raise ValueError(
                f"Condition {key} does not exist in '{self.zip_filepath}'."
            )

        with self.__z.open(filepath) as f:
            return cv2.imdecode(
                np.frombuffer(f.read(), np.uint8),
                cv2.IMREAD_ANYDEPTH + cv2.IMREAD_ANYCOLOR,
            )