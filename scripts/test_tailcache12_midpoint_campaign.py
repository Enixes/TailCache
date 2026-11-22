import copy
import unittest

from tailcache12_midpoint_campaign import adaptive_midpoint


class AdaptiveRuleTest(unittest.TestCase):
    def summary(self,ratios):
        return {'comparisons':[{'liveMiB':live,'passes':[
            {'usable':True,'warnings':{'CAFFEINE':[],'CHRONICLE_IN_MEMORY':[]},
             'ratios':{'response':{'99.9':ratio}}} for ratio in values]}
            for live,values in ratios.items()]}

    def test_only_declared_brackets_can_select_one_midpoint(self):
        self.assertEqual(adaptive_midpoint(self.summary({0:[2,3,4],104:[.8,.7,.9],208:[.2,.3,.4]})),52)
        self.assertEqual(adaptive_midpoint(self.summary({0:[2,3,4],104:[1.1,1.2,1.3],208:[.2,.3,.4]})),156)

    def test_mixed_warned_or_missing_pairs_cannot_trigger_adaptive_search(self):
        base=self.summary({0:[2,3,4],104:[.8,.7,.9],208:[.2,.3,.4]})
        for mode in ('mixed','warned','missing','invalid'):
            data=copy.deepcopy(base);pairs=data['comparisons'][1]['passes']
            if mode=='mixed':pairs[0]['ratios']['response']['99.9']=1.2
            elif mode=='warned':pairs[0]['warnings']['CAFFEINE']=['outside CPU']
            elif mode=='missing':pairs.pop()
            else:pairs[0]['usable']=False
            self.assertIsNone(adaptive_midpoint(data),mode)


if __name__=='__main__':unittest.main()
