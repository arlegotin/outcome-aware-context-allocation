"""Explicit fixture tests for administrative wrapper; no native/Gold observations."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('bounded_wrapper',Path(__file__).resolve().parents[1]/'tools/run_routing_evaluation_bounded.py')
wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)

class WrapperFixtures(unittest.TestCase):
    def invoke(self,mode='success',control_override=None):
        tmp=tempfile.TemporaryDirectory(prefix='oaca-wrapper-fixture-');self.addCleanup(tmp.cleanup)
        base=Path(tmp.name);root=base/'study';root.mkdir();output=base/'output';control=control_override or base/'control'
        state={'ns':0,'remaining':None}
        def clock():
            state['ns']+=1000000
            return state['ns']
        plan={'plan_hash':'3f6124b579d6b27f8b91f7aa7fe4a6fc1ac16c39b69fd96a86f2bdb843291c6b',
              'config':{'schema_version':5,'historical_checkout':str(base/'retained')},
              'denied_paths':[],'source_snapshot_hash':'fixture-only'}
        def publish(p,data):
            Path(p).write_text(json.dumps(data))
        def bounded(command,env,parent,seconds):
            state['remaining']=seconds
            if mode=='timeout':
                state['ns']+=int((seconds+4)*1e9)
                publish(parent/'native-stage-timeout.json',{'group_quiescent':True})
                raise TimeoutError('fixture deadline; owned group cleaned')
            if mode=='unknown_cleanup':
                publish(parent/'native-stage-timeout.json',{'group_quiescent':False})
                raise RuntimeError('fixture unknown cleanup')
            output.mkdir();publish(output/'public-summary.json',{'fixture':True})
            publish(parent/'native-parent-closure.json',{'group_quiescent':True})
            return types.SimpleNamespace(returncode=0)
        modules={}
        package=types.ModuleType('outcome_poc');package.__file__=str(root/'source/src/outcome_poc/__init__.py');package.__path__=[]
        modules['outcome_poc']=package
        for name,fields in {
            'outcome_poc.followup.clock':{'continuous_ns':clock,'boot_identity':lambda:'fixture-boot','clock_identity':lambda:{'fixture':True}},
            'outcome_poc.reader_recovery.allocation_study':{'run_bounded_process':bounded},
            'outcome_poc.reader_recovery.study':{'identity':lambda p:{'fixture_path':str(p)},'read':lambda p:plan,'publish':publish},
        }.items():
            module=types.ModuleType(name);module.__dict__.update(fields);modules[name]=module
        argv=['wrapper','--root',str(root),'--output',str(output),'--control',str(control)]
        with patch.dict(sys.modules,modules),patch.object(sys,'argv',argv):
            error=None
            try:wrapper.main()
            except BaseException as caught:error=caught
        return state,control,error

    def test_success_complete_receipt(self):
        state,control,error=self.invoke()
        self.assertIsNone(error)
        self.assertLessEqual(state['remaining'],594)
        self.assertEqual(json.loads((control/'receipt.json').read_text())['status'],'completed')
        self.assertTrue(json.loads((control/'envelope.json').read_text())['includes_durable_receipt'])

    def test_timeout_cleanup_inside_cap_and_failure_receipt(self):
        _,control,error=self.invoke('timeout')
        self.assertIsInstance(error,TimeoutError)
        self.assertEqual(json.loads((control/'receipt.json').read_text())['status'],'failed')
        envelope=json.loads((control/'envelope.json').read_text())
        self.assertLess(envelope['seconds'],600)
        self.assertTrue(envelope['within_cap'])

    def test_unknown_cleanup_cannot_complete(self):
        _,control,error=self.invoke('unknown_cleanup')
        self.assertIsInstance(error,RuntimeError)
        receipt=json.loads((control/'receipt.json').read_text())
        self.assertEqual(receipt['status'],'failed')
        self.assertIsNotNone(receipt['failure_supervision'])
        self.assertTrue((control/'envelope.json').exists())

    def test_cannot_write_control_inside_evaluator_bundle(self):
        denied=Path('/private/tmp/oaca-routing-evaluation-tools-20261016/fixture-denied-control')
        _,_,error=self.invoke(control_override=denied)
        self.assertIsInstance(error,ValueError)
        self.assertFalse(denied.exists())

if __name__=='__main__':unittest.main(verbosity=2)
