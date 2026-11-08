# Tên cũ, giữ lại để bản cũ vẫn tự cập nhật được. Chương trình chính là mergencut.pyw.
import os
import runpy
import sys

sys.argv[0] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mergencut.pyw")
runpy.run_path(sys.argv[0], run_name="__main__")
