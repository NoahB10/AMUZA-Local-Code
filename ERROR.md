
Traceback (most recent call last):
  File "/usr/lib/python3/dist-packages/pandas/core/indexes/base.py", line 3802, in get_loc
    return self._engine.get_loc(casted_key)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "pandas/_libs/index.pyx", line 138, in pandas._libs.index.IndexEngine.get_loc
  File "pandas/_libs/index.pyx", line 162, in pandas._libs.index.IndexEngine.get_loc
  File "pandas/_libs/index.pyx", line 203, in pandas._libs.index.IndexEngine._get_loc_duplicates
  File "pandas/_libs/index.pyx", line 211, in pandas._libs.index.IndexEngine._maybe_get_bool_indexer
  File "pandas/_libs/index.pyx", line 107, in pandas._libs.index._unpack_bool_indexer
KeyError: '#1ch1'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/usr/lib/python3/dist-packages/matplotlib/backend_bases.py", line 1193, in _on_timer
    ret = func(*args, **kwargs)
          ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3/dist-packages/matplotlib/animation.py", line 1405, in _step
    still_going = super()._step(*args)
                  ^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3/dist-packages/matplotlib/animation.py", line 1098, in _step
    self._draw_next_frame(framedata, self._blit)
  File "/usr/lib/python3/dist-packages/matplotlib/animation.py", line 1117, in _draw_next_frame
    self._draw_frame(framedata)
  File "/usr/lib/python3/dist-packages/matplotlib/animation.py", line 1744, in _draw_frame
    self._drawn_artists = self._func(framedata, *self._args)
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/pi/Documents/AMUZA-Local-Code/Sampling_Collector_Final_Shaun_Changes.py", line 374, in update_plot
    "Glutamate": df["#1ch1"] - df["#1ch2"],
                 ~~^^^^^^^^^
  File "/usr/lib/python3/dist-packages/pandas/core/frame.py", line 3807, in __getitem__
    indexer = self.columns.get_loc(key)
              ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3/dist-packages/pandas/core/indexes/base.py", line 3804, in get_loc
    raise KeyError(key) from err
KeyError: '#1ch1'

Process ended with exit code -6.
