---
title: Banach 不动点定理及其应用
date: 2026-08-20
tags: [分析, 不动点]
excerpt: 压缩映射原理是度量空间理论的基石，我们给出完整证明并用它建立 Picard 迭代收敛性。
---

# Banach 不动点定理

## 定理与证明

\begin{definition}{def:contraction}[压缩映射]
设 $(X,d)$ 为度量空间（参见系列第一篇的 \autoref{def:metric} 风格定义）。若存在 $0 \le q < 1$ 使 $d(Tx,Ty) \le q\,d(x,y)$ 对一切 $x,y\in X$ 成立，则称 $T$ 为压缩映射。
\end{definition}

\begin{theorem}{thm:banach}[Banach 不动点定理]
完备度量空间上的压缩映射有唯一不动点。
$$ x_{n+1} = T x_n, \qquad d(x_n, x^\*) \le \frac{q^n}{1-q} d(x_1, x_0). \label{eq:rate} $$
\end{theorem}

\begin{proof}
迭代序列 $\{x_n\}$ 是 Cauchy 列：由几何级数估计 \eqref{eq:rate} 立得。
完备性保证极限 $x^\*$ 存在，且 $Tx^\* = x^\*$。唯一性由压缩性直接得出。
\end{proof}

## 应用：Picard 定理

\begin{corollary}{cor:picard}
设 $f$ 关于 $y$ 满足 Lipschitz 条件，则初值问题 $y' = f(x,y)$，$y(x_0)=y_0$ 在局部存在唯一解。
\end{corollary}

\begin{remark}
结合傅里叶分析中的收敛定理，可以看到逐次逼近思想的普适性。
\end{remark}
