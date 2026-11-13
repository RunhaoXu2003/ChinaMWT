from pathlib import Path
import json
import numpy as np
from scipy.interpolate import CubicSpline
from .common import APP_ROOT,sha256

class ReferenceModel:
    def __init__(self,path=None):
        self.path=Path(path or APP_ROOT/'reference/reference_model.json')
        self.payload=json.loads(self.path.read_text(encoding='utf-8'))
        self.digest=sha256(self.path)
        self.models=self.payload['models']
        self.splines={}
        for sex,m in self.models.items():
            self.splines[sex]={}
            for variable in ['age','bsa']:
                x=np.array(m[variable]['knots'],float);y=np.array(m[variable]['values'],float)
                if len(x)!=10 or np.any(np.diff(x)<=0):raise ValueError('Frozen spline knots are invalid.')
                self.splines[sex][variable]=CubicSpline(x,y,bc_type='natural')

    def _term(self,sex,variable,x):
        s=self.splines[sex][variable];a,b=s.x[0],s.x[-1]
        x=np.asarray(x,float);result=s(np.clip(x,a,b))
        return np.where(x<a,s(a)+s(a,1)*(x-a),np.where(x>b,s(b)+s(b,1)*(x-b),result))

    def predict(self,sex,age,bsa):
        if sex not in self.models:raise ValueError('请选择模型性别。')
        if not np.isfinite([age,bsa]).all() or bsa<=0:raise ValueError('年龄/BSA必须为有效数值。')
        m=self.models[sex]
        mu=float(m['intercept']+self._term(sex,'age',age)+self._term(sex,'bsa',bsa))
        return mu,float(m['sigma']),float(m['q975'])

    def evaluate(self,mwt,sex,age,height,weight):
        if not np.isfinite([mwt,age,height,weight]).all():raise ValueError('人口学输入包含非有限值。')
        if not 18<=age<=120:raise ValueError('参考模型用于成人，请输入18–120岁的年龄。')
        if not 50<=height<=250:raise ValueError('请核对身高（单位cm）。')
        if not 10<=weight<=400:raise ValueError('请核对体重（单位kg）。')
        bsa=.007184*height**.725*weight**.425;bmi=weight/(height/100)**2
        mu,sigma,q=self.predict(sex,age,bsa);limit=mu+q*sigma;z=(mwt-mu)/sigma
        m=self.models[sex];flags=[]
        if not m['age_range'][0]<=age<=m['age_range'][1]:flags.append('年龄超出参考观测范围')
        if not m['bsa_range'][0]<=bsa<=m['bsa_range'][1]:flags.append('BSA超出参考观测范围')
        if not 18<=bmi<=35:flags.append('BMI超出参考入组范围18–35')
        support=m['support'];i=int(np.searchsorted(support['age_edges'],age,side='right')-1);j=int(np.searchsorted(support['bsa_edges'],bsa,side='right')-1)
        counts=np.asarray(support['counts']);n=int(counts[i,j]) if 0<=i<counts.shape[0] and 0<=j<counts.shape[1] else 0
        if n<5:flags.append(f'当前年龄/BSA单元样本稀疏（n={n}）')
        return dict(mwt_mm=float(mwt),sex=sex,age=float(age),height_cm=float(height),weight_kg=float(weight),bsa_m2=bsa,bmi=bmi,
                    expected_mwt_mm=mu,upper_limit_mm=limit,z_score=z,sigma_mm=sigma,q975=q,above_limit=bool(mwt>=limit),
                    support_cell_n=n,support_flags=flags,reference_sha256=self.digest,
                    definition='Z=(study-rounded patient MWT−population μ)/residual σ; limit=μ+sex-specific empirical q×σ; >= rule.')
