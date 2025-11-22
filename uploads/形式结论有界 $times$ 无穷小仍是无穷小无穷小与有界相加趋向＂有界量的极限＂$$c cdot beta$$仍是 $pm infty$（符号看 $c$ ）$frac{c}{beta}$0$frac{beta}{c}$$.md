#   无限大&& 无穷小



##  一、  直观理解 

- **无穷大** $(+\infty 、-\infty 、 \infty  )$ 负无穷大、正无穷大，绝对值无限增大的变量
  直观：能大过你给的任何具体数： $10 、 100 、 1000 、 10^6 \ldots$ 总能超过去，没有＂天花板＂。
  例如 $f(x)=x^2$ 当 $x \rightarrow \infty$ 时，给你＂目标＂ 1000 ，它能超过；给 1000000 ，也能超过——所以叫＂趋
  向无穷大＂。
- **无穷小**（ $\rightarrow 0$ ）
  直观：能比你给的任何＂很小的具体数＂更接近 $\mathbf{0}$ ： $0.1 、 0.01 、 0.001 \ldots$ 都能压过去。
  例如 $g(x)=\frac{1}{x}$ 当 $x \rightarrow \infty$ 时，给 0.01 ，它能比这更小；给 0.000001 ，也能更小——所以＂趋向 0 ＂。
- **有界**
  直观：永远被某个具体数圈住，比如＂始终在 $[-1000,1000]$ 里面＂。像 $\sin x$ 一直在 $[-1,1]$ 里——这就是＂有界＂。
  记忆：有界 $\approx$ 始终不超过某个＂具体数＂（上界／下界就是＂具体的上限／下限＂）。

------



## 二、  数学定义 

- **有界**（bounded）
  直观：永远被某个具体的上／下界圈住（比如始终在 $[-1000,1000]$ 内）。
  定义（在某邻域内）：存在 $M>0$ ，使得当 $x$ 足够靠近 $a$ 时有 $|f(x)| \leq M$ 。 一直被某个具体常数圈住  $|f(x)| \leq M$
- **无穷小**（infinitesimal）
  直观：能比你给的任何＂小数＂更接近 0 （ $0.1 、 0.01 、 0.001 \ldots$ 都能压过去）。
  定义： $\lim _{x \rightarrow a} \alpha(x)=0$ 。 $: f(x) \rightarrow 0$
- 无穷大（infinite／发散）
  直观：能超过你给的任何＂大数＂$\left(100 、 1000 、 10^6 \ldots\right)$ 。
  定义： $\lim _{x \rightarrow a} \beta(x)=+\infty$ 指对任意 $M>0$ ，充分靠近 $a$ 时有 $\beta(x)>M$（ $-\infty$ 类似）。 $f(x) \rightarrow+\infty(\text { 或 }-\infty)=\text { 给多大目标都能超过 (或小于) 。 }$
- 

**如果感受不到就举一个例子**

| 形式                                                         | 结论                        | 一句话为什么                                   | 例子                                                         |
| :----------------------------------------------------------- | :-------------------------- | :--------------------------------------------- | :----------------------------------------------------------- |
| 有界 $\times$ 无穷小                                         | 无穷小                      |                                                | $x \rightarrow0$ 时， $2x\rightarrow 0$                      |
| 无穷小＋（收敛到 $L$ 的量 有界）                             | $\rightarrow L$             | （ $L+$ 小量）仍靠近 $L$ 。                    | $n \rightarrow \infty$ 时， $3+\frac{1}{n} \rightarrow 3$ 。 |
| $c \cdot \beta, \beta \rightarrow \pm \infty$ $c$为常数      | $\pm \infty$（看 $c$ 符号） | 把＂没有上界＂的量按常数放大／翻号，仍无上界。 | $-5 x \rightarrow-\infty$（ 当 $x \rightarrow+\infty$ ）     |
| $\frac{c}{\beta}, \beta \rightarrow \pm \infty$  $c$为常数   | 0                           | 分母无限大，整体被压到 0 。                    | $\frac{7}{x} \rightarrow 0(x \rightarrow \infty)$.           |
| $\frac{\beta}{c}, c \neq 0$ 常数                             | $\pm \infty$（看符号）      | 无穴大除以非零常数仍无穷大。                   | $\frac{x^2}{10} \rightarrow+\infty$ 。                       |
| $\frac{\alpha}{\beta}, \alpha \rightarrow 0, \beta \rightarrow \infty$ | 0                           | 分子比分母＂增长／減小得慢得多＂。             | $\frac{1 / x}{x}=\frac{1}{x^2} \rightarrow 0$.               |

注：**上表里第二行要求＂有界的那一项本身要收敛＂。仅＂有界＂但不收敛时（比如 $(-1)^n$ ），和无穷小相加未必有极限：$(-1)^n+\frac{1}{n}$ 不收敛。**



------



## 三、运算法则



### 1.无穷大运算规则 

- 无穷大 + 无穷大 $=$ 无穷大：这是最直观的理解，例如 $\infty+\infty=\infty$ 。
- 无穷大 $\times$ 无穷大 $=$ 无穷大：类似地，例如 $\infty \times \infty=\infty$ 。
- 无穷大 + 一个数 $=$ 无穷大：例如，$\infty+5=\infty$ 。
- 一个数 $\times$ 无穷大 $=$ 无穷大：如果这个数是正数，例如 $5 \times \infty=\infty$ 。
- 无穷大－无穷大＝不确定：这属于**未定式**形式，例如 $\infty-\infty$ 没有一个固定的值。
- 无穷大 $\div$ 无穷大 $=$ 不确定：这同样属于**未定义**形式。
- 一个数 $\div$ 无穷大 $=0$ ：例如， $5 \div \infty=0$ 。
- 无穷大 $\div$ 一个数 $=$ 无穷大：如果这个数是正数，例如 $\infty \div 5=\infty$ 。



### 2.常用的无穷小量运算法则

- 和差：无穷小量与无穷小量之和或之差仍是无穷小量。
- 积：
  - 无穷小量与常数的积仍是无穷小量。
  - 无穷小量与任意有界量的乘积仍是无穷小量。

- 商：
  - 无穷小量与非零常数的商仍是无穷小量。
  - 两个无穷小量的商是否为无穷小量、无穷大或一个常数，取决于具体的函数形式。


注意事项
－**未定式**：某些运算组合（如 $\infty-\infty 、 \frac{0}{0} 、 \frac{\infty}{\infty}$ 等）是**未定式**，不能直接进行运算，需要通过特定方法（如洛必达法则）求解。
－区分无穷大和无穷小：无穷大是指变量会无限增大，而无穷小是指变量会无限接近于零。
－与实数运算的区别：无穷大和无穷小量不是实数，不能直接参与实数的加减乘除运算，例如 $\infty+\infty$ 不是一个确定的实数。



### 3.有限个运算

**加／减**

- $L+$ 无穷小 $\rightarrow L$ 。
- $L+(+\infty)=+\infty, L+(-\infty)=-\infty ; L-(+\infty)=-\infty, L-(-\infty)=+\infty$ 。
- $+\infty+(+\infty)=+\infty ;-\infty+(-\infty)=-\infty$ 。
- $+\infty+(-\infty)$ 是不定型；
$+\infty-(+\infty) 、-\infty-(-\infty)$ 也是不定型（结果可能是 0 、有限数、 $\pm \infty$ 或没有极限）。
例： $3+\frac{1}{n} \rightarrow 3 ; n+n \rightarrow+\infty ; n-(n-1) \rightarrow 1$（说明＂$\infty-\infty$＂不确定）。



**乘**

- 常数 $c \neq 0$ 与无穷大：$c \cdot(+\infty)=$（看符号）$\pm \infty$ 。
-  $0 \cdot(+\infty)$ 是不定型（要化简再判）。
- 有界 $\times$ 无穷小 $=$ 无穷小（因为 $|f g| \leq M|g| \rightarrow 0$ ）。
- 有界 $\times$ 无穷大：不一定（可能发散、也可能振荡，没有统一结论）。

​       例： $5 \cdot \frac{1}{n} \rightarrow 0 ; \frac{1}{n} \cdot n \rightarrow 1$（说明＂ $0 \cdot \infty$＂不确定）； $\sin n$ 有界，但 $\sin n \cdot n$ 不收敛到某个数。



**除**

- $\frac{c}{+\infty}=0$（ $c$ 有限）；$\frac{+\infty}{c}=$（看符号）$\pm \infty(c \neq 0)$ 。

- $\frac{\text { 无穷小 }}{\text { 有限非零 }}=$ 无穷小；$\frac{\text { 有限非零 }}{\text { 无穷小 }}=$（按单侧）$\pm \infty$ 。

- $\frac{0}{0}, \frac{\infty}{\infty}$ 是不定型；

  例：$\frac{7}{n} \rightarrow 0 ; \frac{n}{7} \rightarrow+\infty ; \frac{1 / n}{1 / n^2}=n \rightarrow+\infty$（说明＂小小＂不确定）。



**有界的和／积（有限个）**

- 有界＋有界 仍有界；有界 $\times$ 有界 仍有界（乘上界即可）。
  例：$|f| \leq 2,|g| \leq 3 \Rightarrow|f+g| \leq 5,|f g| \leq 6$ 。





### 四  未定式

$$
0 / 0, \quad \infty / \infty, \quad \infty-\infty, \quad 0 \cdot \infty, \quad 1^{\infty}, \quad 0^0, \quad \infty^0
$$


遇到它们，别套规则，先把式子变形（因式分解、通分、有理化、常见等价式等），再求极限。

例子 

-  有限 + 无穷小： $3+\frac{1}{n} \rightarrow 3$ 。

- 同号无穷大相加：$n+n=2 n \rightarrow+\infty$ 。
- $\infty-\infty$ 不定：$n-(n-1) \rightarrow 1$ ；$n-n \rightarrow 0 ; 2 n-n \rightarrow+\infty$ 。
- 有界 $\times$ 无穷小： $100 \cdot \frac{1}{n} \rightarrow 0$ 。
- 常数／无穷大：$\frac{7}{n} \rightarrow 0$ ；无穷大／常数：$\frac{n}{5} \rightarrow+\infty$ 。
- 小小不定：$\frac{1^n / n}{1 / n^2}=n \rightarrow+\infty$ ，而 $\frac{1^5 / n}{1 / n}=1$ 。
