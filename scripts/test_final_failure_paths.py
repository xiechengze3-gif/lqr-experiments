"""Failure-path tests against the frozen learner, without source mutations."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import dare
import final_round as runner


class FailurePaths(unittest.TestCase):
    def setUp(self):
        n=6;a=.5*np.eye(n);b=np.diag([.2,.2,0,0,0,0]);k=.1*np.eye(n)
        _,p=dare(a,b,np.eye(n),np.eye(n))
        p0=solve_discrete_lyapunov((a-b@k).T,np.eye(n)+k.T@k)
        self.s=dict(A=a,B=b,Q=np.eye(n),R=np.eye(n),K0=k,Jstar=float(np.trace(p)),
                    initial_gap=float(np.trace(p0-p)))

    def check_terminal(self,root,label):
        files=list((root/'debug').glob('n*.json'));self.assertEqual(len(files),3)
        for path in files:
            data=json.loads(path.read_text());self.assertEqual(data['meta']['status'],label)
            self.assertEqual(len(data['rows']),2);self.assertEqual(data['rows'][-1]['failure'],label)
            self.assertEqual(data['meta']['actual_transitions'],512+513*16)
            self.assertEqual(data['meta']['planned_transitions'],8*(512+513*16))

    def test_numerical_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runner,'make_system',return_value=self.s),\
             patch.object(runner,'collect',side_effect=np.linalg.LinAlgError('Injected solve failure')):
            root=Path(temp);runner.actor(root,[1],[0],[512],.25,'debug',n=6,rank=2)
            self.check_terminal(root,'numerical_failure')
            for path in (root/'debug').glob('n*.json'):
                self.assertIsNone(json.loads(path.read_text())['rows'][-1]['stable'])

    def test_unstable_controller_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runner,'make_system',return_value=self.s),\
             patch.object(runner,'update',return_value=(-10*np.eye(6),{'update_relative_residual':0.,'R_plus_G_condition':1.})):
            root=Path(temp);runner.actor(root,[1],[0],[512],.25,'debug',n=6,rank=2)
            self.check_terminal(root,'controller_instability')
            for path in (root/'debug').glob('n*.json'):
                self.assertFalse(json.loads(path.read_text())['rows'][-1]['stable'])
                with np.load(path.with_suffix('.npz')) as d:np.testing.assert_array_equal(d['K'],-10*np.eye(6))


if __name__=='__main__':unittest.main(verbosity=2)
