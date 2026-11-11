# X11 construction audit before numerical execution

The accepted X6a/X10a family-S constructor explicitly assumes n=m in V's RNG
namespace and dimension, B, K0, R and certificate metadata. This notice is
published before any X11 numerical execution, as the 13:15 Claude GO requires.

Proposed minimal rectangular extension: preserve A and U exactly at fixed n and
system, use V=haar(rng(3,n,m,system),m), B=U[:,:2]@V[:,:2].T,
Q=W=I_n, R=I_m and K0=zeros(m,n). The bound is dimension-independent:
K0=0 gives P0=sum (A^t)' A^t and ||P0||<=1/(1-0.6^2)=1.5625<2.
All square n=m inputs recover the original constructor and RNG namespace.
The original CE collector already supports rectangular (n,m), as does its
OLS and SVD-truncated LQR learner. These functions will be preserved verbatim.

Before FORMAL, fixed pilot checks must establish square model byte equality,
rectangular dimensions/rank/certificate, CE fit/learner identity against the
original generic CE implementation, exact RNG/counts and one BLAS thread.
The duplicated (48,16) sweep cell is collected once and reused in both panels.
No old configuration is resampled. Claude may revise this construction in the
review log; reread that log before advancing each stage.

No X11 numerical work has run at publication of this notice.
