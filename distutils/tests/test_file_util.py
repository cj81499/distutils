"""Tests for distutils.file_util."""

import os
import errno
import unittest.mock as mock

import jaraco.path
import path
import pytest

from distutils.file_util import move_file, copy_file
from distutils.tests import support
from distutils.errors import DistutilsFileError
from .py38compat import unlink


@pytest.fixture(autouse=True)
def stuff(request, tmp_path):
    self = request.instance
    tmp_dir = path.Path(tmp_path)
    self.source = tmp_dir / 'f1'
    self.target = tmp_dir / 'f2'
    self.target_dir = tmp_dir / 'd1'


class TestFileUtil:
    def test_move_file_verbosity(self, caplog):
        jaraco.path.build({self.source: 'some content'})

        move_file(self.source, self.target, verbose=0)
        assert not caplog.messages

        # back to original state
        move_file(self.target, self.source, verbose=0)

        move_file(self.source, self.target, verbose=1)
        wanted = [f'moving {self.source} -> {self.target}']
        assert caplog.messages == wanted

        # back to original state
        move_file(self.target, self.source, verbose=0)

        caplog.clear()
        # now the target is a dir
        os.mkdir(self.target_dir)
        move_file(self.source, self.target_dir, verbose=1)
        wanted = [f'moving {self.source} -> {self.target_dir}']
        assert caplog.messages == wanted

    def test_move_file_exception_unpacking_rename(self):
        # see issue 22182
        with mock.patch("os.rename", side_effect=OSError("wrong", 1)), pytest.raises(
            DistutilsFileError
        ):
            jaraco.path.build({self.source: 'spam eggs'})
            move_file(self.source, self.target, verbose=0)

    def test_move_file_exception_unpacking_unlink(self):
        # see issue 22182
        with mock.patch(
            "os.rename", side_effect=OSError(errno.EXDEV, "wrong")
        ), mock.patch("os.unlink", side_effect=OSError("wrong", 1)), pytest.raises(
            DistutilsFileError
        ):
            jaraco.path.build({self.source: 'spam eggs'})
            move_file(self.source, self.target, verbose=0)

    def test_copy_file_hard_link(self):
        jaraco.path.build({self.source: 'some content'})
        # Check first that copy_file() will not fall back on copying the file
        # instead of creating the hard link.
        try:
            self.source.link(self.target)
        except OSError as e:
            self.skipTest('os.link: %s' % e)
        else:
            self.target.unlink()
        st = os.stat(self.source)
        copy_file(self.source, self.target, link='hard')
        st2 = os.stat(self.source)
        st3 = os.stat(self.target)
        assert os.path.samestat(st, st2), (st, st2)
        assert os.path.samestat(st2, st3), (st2, st3)
        assert self.source.read_text(encoding='utf-8') == 'some content'

    def test_copy_file_hard_link_failure(self):
        # If hard linking fails, copy_file() falls back on copying file
        # (some special filesystems don't support hard linking even under
        #  Unix, see issue #8876).
        jaraco.path.build({self.source: 'some content'})
        st = os.stat(self.source)
        with mock.patch("os.link", side_effect=OSError(0, "linking unsupported")):
            copy_file(self.source, self.target, link='hard')
        st2 = os.stat(self.source)
        st3 = os.stat(self.target)
        assert os.path.samestat(st, st2), (st, st2)
        assert not os.path.samestat(st2, st3), (st2, st3)
        for fn in (self.source, self.target):
            assert fn.read_text(encoding='utf-8') == 'some content'
