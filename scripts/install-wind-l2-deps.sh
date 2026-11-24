#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"
source_dir="$(mktemp -d "${repo_root}/var/tmp/baidupcs-py.XXXXXX")"
trap 'rm -rf "${source_dir}"' EXIT

"${python_bin}" -m pip install --index-url https://pypi.org/simple \
  'setuptools==69.5.1' 'Cython==3.0.12' 'wheel==0.45.1' 'poetry-core==1.9.0'
"${python_bin}" -m pip install --index-url https://pypi.org/simple -e "${repo_root}[wind-l2]"

git clone --filter=blob:none https://github.com/PeterDing/BaiduPCS-Py.git "${source_dir}"
git -C "${source_dir}" checkout e81e9b65c4b35fc8f7f2993a81e25e0bc24608db
# 上游构建脚本调用 setuptools 自动发现；文档图片目录会被误判为第二个顶层包。
rm -rf "${source_dir}/imgs"
cp "${repo_root}/vendor/baidupcs_simple_cipher.py" \
  "${source_dir}/baidupcs_py/common/simple_cipher.py"
TEMP="${repo_root}/var/tmp" TMP="${repo_root}/var/tmp" \
  "${python_bin}" -m pip install --index-url https://pypi.org/simple \
  --no-build-isolation --no-deps "${source_dir}"

"${python_bin}" -c 'from baidupcs_py.baidupcs import BaiduPCSApi; print("BaiduPCS-Py ready")'
