"""BaiduPCS-Py simple_cipher.pyx 的等价纯 Python 实现。

上游源码构建在 Python 3.12/Linux 下不会把 Cython 扩展装入 wheel；这里只补齐同名模块。
原项目使用 MIT License：https://github.com/PeterDing/BaiduPCS-Py
"""

import random


class SimpleCryptography:
    def __init__(self, key):
        generator = random.Random()
        generator.seed(key, version=2)
        byte_map = list(range(256))
        generator.shuffle(byte_map)
        self._encrypt_byte_map = bytes(byte_map)
        self._decrypt_byte_map = bytes(
            value for _, value in sorted(zip(byte_map, range(256), strict=True))
        )
        self._key = key

    @staticmethod
    def _translate(data, byte_map):
        return bytes(byte_map[value] for value in bytearray(data))

    def encrypt(self, data):
        return self._translate(data, self._encrypt_byte_map)

    def decrypt(self, data):
        return self._translate(data, self._decrypt_byte_map)

    def reset(self):
        pass
