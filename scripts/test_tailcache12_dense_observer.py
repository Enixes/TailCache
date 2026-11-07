import csv
import pathlib
import tempfile
import unittest
from tailcache12_dense_observer import replay,validate_controls,VERSION


class DenseObserverTest(unittest.TestCase):
    def fixture(self,root):
        target=root/'dense-observer';target.mkdir()
        (target/'configuration.txt').write_text('version='+VERSION+'\nwarmups=1\nphysicalMeasurements=1\nconditioning=0\nhistogramSignificantDigits=3\nhistogramMaxNs=60000000000\n')
        columns=['phase','iteration','startNs','endNs','operations','serviceAbove1ms','gapAbove1ms','serviceAbove10ms','gapAbove10ms','serviceMaxNs','completionGapMaxNs','eventCount','overflowCount']
        rows=[dict(zip(columns,[p,1,a,b,1600,0,0,0,0,10,10,0,0])) for p,a,b in [('WARMUP',1000,100000),('MEASUREMENT',200000,300000)]]
        with (target/'iterations.csv').open('w') as f:
            writer=csv.DictWriter(f,columns);writer.writeheader();writer.writerows(rows)
        for channel in ('service','completion-gap'):
            (target/f'iteration-1-{channel}-bins.csv').write_text('upperEquivalentNs,count\n10,1600\n')
            (target/f'iteration-1-{channel}.hdr').write_bytes(b'fixture-secondary-hdr')
        (target/'iteration-1-stall-events.csv').write_text('serviceStartNs,endNs,previousCompletionNs,serviceNs,completionGapNs\n')
        parents=[dict(phase=r['phase'],operations='1601',envelopeStartNs=str(int(r['startNs'])-10),envelopeEndNs=str(int(r['endNs'])+10)) for r in rows]
        return target,dict(Warmups=1,Measurements=1),parents

    def test_phase_histogram_stall_and_sampling_conservation_fail_closed(self):
        for mutation in ('none','bin-loss','event-loss','extra','sampling','envelope'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=pathlib.Path(tmp);path,inputs,parents=self.fixture(root);samples=[100]
                if mutation=='bin-loss':(path/'iteration-1-service-bins.csv').write_text('upperEquivalentNs,count\n10,1599\n')
                if mutation=='event-loss':
                    text=(path/'iterations.csv').read_text();(path/'iterations.csv').write_text(text.replace('10,10,0,0','10,10,1,0'))
                if mutation=='extra':(path/'unexplained').write_text('extra')
                if mutation=='sampling':samples=[200]
                if mutation=='envelope':parents[-1]['envelopeStartNs']='250000'
                if mutation=='none':self.assertEqual(replay(root,inputs,parents,samples)['operations'],1600)
                else:
                    with self.assertRaises(ValueError):replay(root,inputs,parents,samples)

    def test_diagnostic_capture_never_supplies_ordinary_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);args=['-Dtailcache12.denseObserver=true','-Dtailcache12.observerDiagnosticOnly=true']
            props=dict(DenseObserver='true',ObserverDiagnosticOnly='true');selection=dict(denseObserverWork=True)
            validate_controls([],{},None,root)
            validate_controls(args,props,selection,root,True)
            for flags,inputs,record,allowed in ((args,props,selection,False),([],props,selection,True),(args,props,None,True),(args,{},selection,True)):
                with self.assertRaises(ValueError):validate_controls(flags,inputs,record,root,allowed)


if __name__=='__main__':unittest.main()
