# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Static descriptions of the reason why each linter was triggered."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pprint
import pydoc
import re

import linters


FMT_FN = 'format_warnings'

MAX_WIDTH = 80
MAX_LEN = 30
FLAG_PREAMBLE = 'Flagged features:'
FLAG_SAMPS_PREAMBLE = 'Flagged features (and sample values):'
LI = '* {}'
LI_SAMP = LI + ': {}'
COLSEP = ' | '
BORDER_SZ = len('| {} |'.format(' '))
PCT_FMT = '{:.3n}%'

ULL_WFMT = LI + ': {} had length {} but {} had {}.'
NFNR_PREAMBLE = ('A \'typical\' numeric feature in the dataset has mean {:.3n}'
                 ' and std dev {:.5n} but')
NFNR_WFMT = LI + ' had {}'
NFNR_STATFMT = '{} = {:.5n}'
DD_PREAMBLE = 'Found {} exact duplicate examples, {} of which are shown below.'
DD_MAX_VAL_LEN = 20
DD_MAX_COLS = 30
USD_PREAMBLE = 'Flagged features and prevalence of uncommon sign(s):'
USD_WFMT = '{} occurred {} of the time'
TDD_PREAMBLE = 'Flagged features and outlying extrema:'
TDD_WFMT = '{} value of {:.3n}'


def formatter(cls):
  def set_formatter(fn):
    setattr(cls, FMT_FN, staticmethod(fn))
    return fn
  return set_formatter


def pformat(obj, max_len=MAX_LEN, quote=True):
  """Pretty prints an object."""
  if hasattr(obj, '__len__') and len(obj) == 1:
    obj = obj[0]
  if isinstance(obj, (int, float)):
    pstr = '{:.4n}'.format(obj)
  else:
    pstr = pprint.pformat(obj)
  pstr = re.sub(r'u(["\'])', r'\1', pstr)
  if not quote:
    pstr = pstr.strip("'").strip('"')
  pstr = pydoc.cram(pstr, max_len)
  return pstr


def _format_warning_sample_pair(warning, sample, quote_vals=True):
  wstr = pformat(warning, quote=False)
  samp_vals = sample.strings or sample.nums
  samp_str = ', '.join([pformat(v, quote=quote_vals) for v in samp_vals])
  return LI_SAMP.format(wstr, samp_str if samp_vals else wstr)


@formatter(linters.LintDetector)
def _format_warnings(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """Generic string formatter for warnings and, optionally, samples.

  Args:
    result: a LintResult proto produced by this linter
    suppress: a set of warnings to be suppressed for this linter
    max_width: the maximum width of a line generated by this formatter

  Returns:
    A list of lines to be printed.
  """
  if result.lint_samples:
    lines = [FLAG_SAMPS_PREAMBLE]
    for warning, samp in zip(result.warnings, result.lint_samples):
      if warning in suppress:
        continue
      lines.append(_format_warning_sample_pair(warning, samp))
  else:
    wstrs = [LI.format(pformat(w)) for w in result.warnings]
    lines = [FLAG_PREAMBLE, '\n'.join(wstrs)]
  return lines


@formatter(linters.EnumDetector)
def _format_warnings_de(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for EnumDetector LintResults."""
  lines = [FLAG_SAMPS_PREAMBLE]
  for warning, samp in zip(result.warnings, result.lint_samples):
    if warning in suppress:
      continue
    lines.append(_format_warning_sample_pair(warning, samp, False))
  return lines


@formatter(linters.UncommonListLengthDetector)
def _format_warnings_llo(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for UncommonListLengthDetector LintResults."""
  lines = [FLAG_PREAMBLE]
  for warning, sample in zip(result.warnings, result.lint_samples):
    if warning in suppress:
      continue

    n_egs = sample.nums[0]
    bucket_pcts = [PCT_FMT.format(bucket.count / n_egs * 100)
                   for bucket in sample.stats]

    bucket_bounds = [' to '.join(map('{:.0f}'.format,
                                     sorted({bucket.min, bucket.max})))
                     for bucket in sample.stats]

    pct_bounds = map(list, zip(bucket_pcts, bucket_bounds))
    lines.append(ULL_WFMT.format(pformat(warning, quote=False),
                                 *sum(pct_bounds, [])))
  return lines


@formatter(linters.EmptyExampleDetector)
def _format_warnings_dee(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for EmptyExampleDetector LintResults."""
  return ['Found {} empty examples.'.format(result.warnings[0])]


@formatter(linters.NonNormalNumericFeatureDetector)
def _format_warnings_nfnr(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for NonNormalNumericFeatureDetector LintResults."""
  ds_stats = result.lint_samples[0].stats[0]
  lines = [NFNR_PREAMBLE.format(ds_stats.mean, ds_stats.std_dev)]
  for warning, sample in zip(result.warnings, result.lint_samples[1:]):
    warned_feature, warning_stats = warning.split(':')
    warned_stats = warning_stats.split(',')
    if warned_feature in suppress:
      continue
    stats = sample.stats[0]
    stats_warnings = [
        NFNR_STATFMT.format(warned_stat, getattr(stats, warned_stat))
        for warned_stat in warned_stats]
    lines.append(NFNR_WFMT.format(pformat(warned_feature, quote=False),
                                  ', '.join(stats_warnings)))
  return lines


@formatter(linters.DuplicateExampleDetector)
def _format_warnings_dd(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for DuplicateExampleDetector LintResults."""
  egs = result.lint_samples[0].examples
  lines = [DD_PREAMBLE.format(result.warnings[0], len(egs))]
  cols = sorted(set(f for eg in egs for f in eg.features.feature))[:DD_MAX_COLS]
  col_vals = {col: [] for col in cols}
  col_widths = {col: min(len(col), DD_MAX_VAL_LEN - BORDER_SZ) for col in cols}
  for eg in egs:
    for col in cols:
      feature = eg.features.feature.get(col)
      if not feature:
        col_vals[col].append('')
        continue
      kind = feature.WhichOneof('kind')
      if kind is None:
        col_vals[col].append('')
        continue
      vals = getattr(feature, kind).value
      if not vals:
        col_vals[col].append('')
        continue
      val_str = pformat(vals, max_len=DD_MAX_VAL_LEN)
      col_vals[col].append(val_str)
      col_widths[col] = max(col_widths[col], min(len(val_str), DD_MAX_VAL_LEN))

  col_groups = [[]]
  tot_width = 0
  for col in cols:
    colwidth = col_widths[col] + BORDER_SZ
    if tot_width + colwidth >= max_width:
      col_groups.append([col])
      tot_width = 0
    else:
      col_groups[-1].append(col)
      tot_width += colwidth

  col_group_strs = []
  for i, col_group in enumerate(col_groups, 1):
    if i == 1:
      borders = '| {} ' + ('|' if len(col_groups) == 1 else '')
    elif i < len(col_groups):
      borders = ' {} '
    else:
      borders = ' {} |'

    heading = borders.format(
        COLSEP.join(pydoc.cram(c, col_widths[c]).center(col_widths[c])
                    for c in col_group))
    hrule = '-' * len(heading)
    cg_lines = [hrule, heading, hrule]
    for j in range(len(egs)):
      l = borders.format(
          COLSEP.join(col_vals[c][j].center(col_widths[c]) for c in col_group))
      cg_lines.append(l)
    cg_lines.append(hrule)
    col_group_strs.append('\n'.join(cg_lines))

  lines.append('\n\n'.join(col_group_strs))

  return lines


@formatter(linters.UncommonSignDetector)
def _format_warnings_dus(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for UncommonSignDetector LintResults."""
  lines = [USD_PREAMBLE]
  for warning, sample in zip(result.warnings, result.lint_samples):
    if warning in suppress:
      continue
    num_unique_vals = sample.nums[0]
    wstrs = []
    for sign_str, sign_count in zip(sample.strings, sample.nums[1:]):
      pct_w_sign = sign_count / num_unique_vals * 100
      if pct_w_sign >= 1:
        pct_str = PCT_FMT.format(pct_w_sign)
      else:
        pct_str = '< 1%'
      wstrs.append(USD_WFMT.format(sign_str, pct_str))
    lines.append(LI_SAMP.format(pformat(warning, quote=False),
                                ', '.join(wstrs)))
  return lines


@formatter(linters.TailedDistributionDetector)
def _format_warnings_don(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for TailedDistributionDetector LintResults."""
  lines = [TDD_PREAMBLE]
  for warning, sample in zip(result.warnings, result.lint_samples):
    if warning in suppress:
      continue
    stats = sample.stats[0]
    extremes = stats.id.split(',')
    extremal = [getattr(stats, e) for e in extremes]
    wstrs = [TDD_WFMT.format(e, float(ev)) for e, ev in zip(extremes, extremal)]
    lines.append(LI_SAMP.format(pformat(warning, quote=False),
                                ', '.join(wstrs)))
  return lines


@formatter(linters.IntAsFloatDetector)
def _format_warnings_iaf(result, suppress=frozenset(), max_width=MAX_WIDTH):
  """String formatter for IntAsFloatDetector LintResults."""
  wstrs = [LI.format(pformat(warning, quote=False))
           for warning in result.warnings]
  lines = [FLAG_PREAMBLE, '\n'.join(wstrs)]
  return lines


linters.DateTimeAsStringDetector.DESCRIPTION = """
A feature flagged by this linter contains strings that might represent dates
or times.

This is a lint because feeding the string directly into a model will cause each
unique date[time] to become its own feature. This is fine if there are only a
few unique values but the linear progression of time would be better modeled if
the feature were represented as a number.

Quickfix: convert the feature to a timestamp.
"""


linters.TokenizableStringDetector.DESCRIPTION = """
A feature flagged by this linter often contains long strings that have more
than a handful of unique values.
This suggests that the feature might have compositional structure that is
may usefully be exposed to the model. For instance, a sentence may be better
understood as a sequence (or even set) of words.

Quickfix: [tokenize](https://nlp.stanford.edu/IR-book/html/htmledition/tokenization-1.html) the strings.
The tokens can then be used as, for instance, a
[bag of words](https://en.wikipedia.org/wiki/Bag-of-words_model) or the inputs
to an [embedding layer](https://github.com/tflearn/tflearn/blob/master/examples/nlp/lstm.py).
"""


linters.NumberAsStringDetector.DESCRIPTION = """
A feature flagged by this linter often takes values that look like numbers.
For instance, it could contain simple floats, dollar values, or percents.

Quickfix: unless the feature represents a categorical value, it would be better
represented to the model as the number, itself.
"""


linters.ZipCodeAsNumberDetector.DESCRIPTION = """
A feature flagged by this linter is likely a zip code and should be represented
as a categorical value since there is no numerical relation between zip codes.

Quickfix: represent the zip code as a string.
"""


linters.NonNormalNumericFeatureDetector.DESCRIPTION = """
A feature flagged by this linter has a distribution that varies significantly
from the other numeric features.
Especially for linear models, poorly scaled features with high variance
(e.g., all but one are in the range [-10, 10] but one is in [0, 100000])
can wash out the effects of the other features.

Quickfix: use the [standard score](https://en.wikipedia.org/wiki/Standard_score)
of (at least) the flagged features.
"""


linters.IntAsFloatDetector.DESCRIPTION = """
While this is not, itself, a lint, it may be indicative of a feature that might
actually be categorical (and that the enum_threshold isn't set high enough).
"""


linters.EnumDetector.DESCRIPTION = """
A feature flagged by this linter is numeric but only takes on a few values.
If this is generally the case (and not just an artifact of most values being
missing), it might be helpful to treat the feature as a categorical variable and
treat each unique value as its own boolean feature.

Quickfix: split the feature into N boolean features or index the values and use
them as the input to an embedding layer.
"""


linters.UncommonListLengthDetector.DESCRIPTION = """
A feature flagged by this linter has `value` lists that are not smoothly
distributed with respect to their length. For instance, most `value`s could have
length 3 but one has length 2. This could be a typo.

Quickfix: ensure that you mean to have variable length lists and that the model
is equipped to handle them.
"""


linters.DuplicateExampleDetector.DESCRIPTION = """
This linter finds exactly duplicated Examples. It's possible that your data
generation process actually permits duplicates or they're the result of missing
entries.  For spurious duplicates, a few are usually fine, but a large number or
Examples shared across train/val/test can be problematic and should be filtered.

Quickfix: remove all but one of each Example.
"""


linters.EmptyExampleDetector.DESCRIPTION = """
This linter detects completely empty examples. These are possibly indicative of
data entry errors.

Quickfix: remove all empty examples.
"""


linters.UncommonSignDetector.DESCRIPTION = """
A feature flagged by this linter has a handful of values that have a different
sign (+/-/0/nan) from the rest. These may be the result of incorrectly entering
the values or using a custom "missing" value like -999.

Quickfix: ensure that values are valid and, if not, replace them with a
standard missing value of either an empty values list or an explicit nan.
"""


linters.TailedDistributionDetector.DESCRIPTION = """
A feature flagged by this linter has an extremal value that significantly
affects the mean. This may be because the value is an outlier but it may also
be due to the extremal value being very common. In either case, however, it
would be beneficial to check the histograms to ensure that they follow the
expected distribution.

Quickfix: check the histograms of the feature values.
"""


linters.CircularDomainDetector.DESCRIPTION = """
A feature flagged by this linter is likely to contain values that wrap around.
For instance, angle (0 and 360 are close), hour, and latitude/longitude.
Feeding these directly into a linear model may yield incorrect results since
it does not take into account the modulus.

Quickfix: quantize the feature values and make each bucket its own
feature/embedding index.
"""