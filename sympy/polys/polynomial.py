
from sympy.core.add import Add
from sympy.core.mul import Mul
from sympy.core.power import Pow
from sympy.core.symbol import Symbol
from sympy.core.sympify import sympify
from sympy.core.basic import Basic, S, C
from sympy.core.methods import RelMeths, ArithMeths

from sympy.utilities import all, any
from sympy.simplify import cancel # TBD : move cancel() to algorithms.py

from sympy.polys.monomial import monomial_cmp, \
    monomial_mul, monomial_max, monomial_as_basic

import sympy.polys

import math

class PolynomialError(Exception):
    pass

##
## TODO:
##
##  [!] Copy + Write tests for everything.
##  [2] Analyze dense MV multiplication.
##  [~] Create MV poly with int coeffs.
##  [4] Think on GF polys (for factoring).
##  [5] Improve coefficients analysis.
##  [6] Implement FactoredPoly.
##  [7] Concept of Monomial.
##  [8] Generalize some polynomial functions, like factor(),
##      to rational expressions. Move at least cancel() and
##      maybe apart() to polys.fraction (or similar).
##

class Poly(Basic, RelMeths, ArithMeths):
    """Represents polynomials with symbolic coefficients.

       Polynomials are internally represented as two lists containing
       coefficients and monomials (tuples of exponents) respectively.
       Stored are only terms with non-zero coefficients, so generally
       all polynomials are considered sparse. However algorithms will
       detect dense polynomials and used appropriate method, to solve
       the given problem in most efficient way.

       The most common way to initialize a polynomial instance is to
       provide a valid expression together witch a set of ordered
       symbols and, additionally, monomial ordering:

            Poly(expression, x_1, x_2, ..., x_n, order='grlex')

       If the given expression is not a polynomial with respect to
       the given variables, an exception is raised. Alternatively
       you can use Basic.as_poly to avoid exception handling.

       By default ordering of monomials can be omitted. In this case
       graded lexicographic order will be used. Anyway remember that
       'order' is a keyword argument.

       Currently there are supported four standard orderings:

           [1] lex       -> lexicographic order
           [2] grlex     -> graded lex order
           [3] grevlex   -> reversed grlex order
           [4] 1-el      -> first elimination order

       Polynomial can be also constructed explicitly by specifying
       a collection of coefficients and monomials. This can be done
       in at least three different ways:

           [1] [(c_1, M_1), (c_2, M_2), ..., (c_1, M_1)]

           [2] (c_1, c2, ..., c_n), (M_1, M_2, ..., M_n)

           [3] { M_1 : c_1, M_2 : c_2, ..., M_n : c_n }

       Although all three representation look similar, they are
       designed for different tasks and have specific properties:

           [1] All coefficients and monomials  are validated before
               polynomial instance is created. Monomials are sorted
               with respect to the given order.

           [2] No validity checking, no sorting, just a raw copy.

           [3] Also no validity checking however monomials are
               sorted with respect to the given order.

       For interactive usage choose [1] as it's safe and relatively
       fast. Use [2] or [3] internally for time critical algorithms,
       when you know that coefficients and monomials will be valid.

       Implemented methods:

           U --> handles uniformly int | long and Basic coefficients
                 (other methods need to be overridden in IntegerPoly)

           P --> a property (with appropriate decorator)

           - --> otherwise

       [1] Representation conversion:

          [1.1] [--] as_basic   --> converts to a valid sympy expression
          [1.2] [U-] as_dict    --> returns { M_1 : c_1, ..., M_1 : c_1 }
          [1.3] [U-] as_uv_dict --> returns dict with integer keys

       [2] Polynomial internals:

          [2.1] [UP] coeffs  --> list of coefficients
          [2.2] [UP] monoms  --> list of monomials
          [2.3] [UP] symbols --> an ordered list of symbols
          [2.4] [UP] order   --> the ordering of monomials
          [2.5] [UP] stamp   --> frozen set of polynomial's variables
          [2.6] [UP] domain  --> coefficient domain, see [8] for details
          [2.7] [UP] args    --> required for printing and hashing
          [2.8] [UP] flags   --> dict of keyword arguments to Poly

       [3] General characteristics:

          [3.1] [UP] norm         --> computes oo-norm of coefficients
          [3.2] [UP] length       --> counts the total number of terms
          [3.3] [UP] degree       --> returns degree of the leading monomial
          [3.4] [UP] total_degree --> returns true total degree of a polynomial

       [4] Items generators:

          [4.1] [U-] iter_coeffs --> iterate over coefficients
          [4.2] [U-] iter_monoms --> iterate over monomials
          [4.3] [U-] iter_terms  --> iterate over terms

       [5] Leading items:

          [5.1] [UP] lead_coeff or LC --> returns leading coefficient
          [5.2] [UP] lead_monom or LM --> returns leading monomial
          [5.3] [UP] lead_term  or LT --> returns leading term

       [6] Arithmetic operators:

          [6.1]  [U-] __abs__     --> for all i, abs(c_i)
          [6.2]  [U-] __neg__     --> polynomial negation
          [6.3]  [U-] __add__     --> polynomial addition
          [6.4]  [U-] __sub__     --> polynomial subtraction
          [6.5]  [--] __mul__     --> polynomial multiplication
          [6.6]  [U-] __pow__     --> polynomial exponentiation
          [6.7]  [U-] __div__     --> polynomial quotient
          [6.8]  [U-] __mod__     --> polynomial remainder
          [6.9]  [U-] __divmod__  --> both 'div' and 'mod'
          [6.10] [U-] __truediv__ --> the same as 'div'

       [7] Polynomial properties:

          [7.1]  [UP] is_zero          --> only one term c_0 == 0
          [7.2]  [UP] is_one           --> only one term c_0 == 1
          [7.3]  [UP] is_constant      --> convertible to a value
          [7.4]  [UP] is_monomial      --> number of terms == 1
          [7.5]  [UP] is_univariate    --> number of variables = 1
          [7.6]  [UP] is_multivariate  --> number of variables > 1
          [7.7]  [UP] is_homogeneous   --> has constant term
          [7.8]  [UP] is_inhomogeneous --> no constant term
          [7.9]  [UP] is_sparse        --> filled with less than 90% of terms
          [7.10] [UP] is_dense         --> filled with more than 90% of terms
          [7.12] [UP] is_monic         --> returns True if leading coeff is one
          [7.11] [UP] is_primitive     --> returns True if content is one

       [8] Coefficients properties:

          [8.1] [UP] has_integer_coeffs  --> for all i, c_i in Z
          [8.2] [UP] has_rational_coeffs --> for all i, c_i in Q
          [8.3] [UP] has_radical_coeffs  --> for all i, c_i in R
          [8.4] [UP] has_complex_coeffs  --> for all i, c_i in C
          [8.5] [UP] has_symbolic_coeffs --> otherwise

       [9] Special functionality:

          [9.1] [--] as_monic     --> divides all coefficients by LC

          [9.2] [-P] content      --> returns GCD of polynomial coefficients
          [9.3] [--] as_primitive --> returns content and primitive part

          [9.4] [--] map_coeffs   --> applies a function to all coefficients
          [9.5] [UP] coeff        --> returns coefficient of the given monomial

          [9.5] [--] map_coeffs    --> applies a function to all coefficients
          [9.6] [U-] coeff         --> returns coefficient of the given monomial

          [9.7] [U-] unify_with    --> returns polys with a common set of symbols

          [9.8] [U-] diff          --> efficient polynomial differentiation
          [9.9] [U-] integrate     --> efficient polynomial integration

       [10] Operations on terms:

          [10.1] [U-] add_term --> add particular term to a polynomial
          [10.2] [U-] sub_term --> subtract particular term from a polynomial

          [10.3] [U-] remove_lead_term --> remove leading term (up to order)
          [10.4] [U-] remove_last_term --> remove last term (up to order)

       [11] Substitution and evaluation:

          [11.1] [U-] __call__    --> evaluates poly a the given point
          [11.2] [U-] evaluate    --> evaluates poly for specific vars
          [11.3] [--] _eval_subs  --> efficiently substitute variables

       [12] Comparison functions:

          [12.1] [U-] __eq__      --> P1 == P, up to order of monomials
          [12.2] [U-] __ne__      --> P1 != P, up to order of monomials
          [12.3] [U-] __nonzero__ --> check if zero polynomial

       [13] Other functionality:

          [13.1] [U-] _eval_is_polynomial --> checks if poly is a poly

       For general information on polynomials and algorithms, refer to:

       [1] D. E. Knuth, The Art of Computer Programming: Seminumerical
           Algorithms, v.2, Addison-Wesley Professional, 1997

       [2] J. von zur Gathen, J. Gerhard, Modern Computer Algebra,
           Second Edition, Cambridge University Press, 2003

       [3] K. Geddes, S. R. Czapor, G. Labahn, Algorithms for
           Computer Algebra, Springer, 1992

       [4] D. Bini, V. Y.Pan, Polynomial and Matrix Computations:
           Volume 1: Fundamental Algorithms, Birkhauser Boston, 1994

       [5] R. T. Moenck, Practical Fast Polynomial Multiplication,
           Proceedings of the third ACM symposium on Symbolic and
           algebraic computation, ACM Press, Yorktown Heights,
           New York, USA, 1976, pp. 136-148

       [6] M. Bronstein, Symbolic Integration I: Transcendental
           Functions, Second Edition, Springer-Verlang, 2005

       See also documentation of particular methods.

    """

    def __new__(cls, poly, *symbols, **flags):
        N, terms = len(symbols), {}
        stamp = frozenset(symbols)
        coeffs, monoms = (), ()

        if N == 0 or len(stamp) != N:
            raise PolynomialError

        order = flags.pop('order', 'grlex')

        # { M1: c1, M2: c2, ... }
        if type(poly) is dict:
            if not poly:
                coeffs = (S.Zero,)
                monoms = ((0,) * N,)
            else:
                terms = poly

        # ((c1, c2, ...), (M1, M2, ...))
        elif type(poly) is tuple:
            if not poly:
                coeffs = (S.Zero,)
                monoms = ((0,) * N,)
            else:
                if len(poly) == 2:
                    coeffs, monoms = poly[0], poly[1]

                    if isinstance(coeffs, (tuple, list)):
                        if not (coeffs or monoms):
                            coeffs = (S.Zero,)
                            monoms = ((0,) * N,)
                    else:
                        coeffs = (coeffs,)
                        monoms = (monoms,)
                else:
                    raise PolynomialError

        # [ (c1,M1), (c2,M2), ... ]
        elif type(poly) is list:
            if not poly:
                coeffs = (S.Zero,)
                monoms = ((0,) * N,)
            else:
                for coeff, monom in poly:
                    coeff = sympify(coeff)

                    if coeff.has_any_symbols(*symbols):
                        raise PolynomialError

                    if type(monom) is int:
                        monom = (monom,)

                    if len(monom) != N:
                        raise PolynomialError

                    if not coeff:
                        continue

                    if terms.has_key(monom):
                        coeff += terms[monom]

                        if not coeff:
                            del terms[monom]
                            continue

                    terms[monom] = coeff

                if not terms:
                    coeffs = (S.Zero,)
                    monoms = ((0,) * N,)
        elif isinstance(poly, Poly):
            if stamp <= poly.stamp:
                if symbols == poly.symbols:
                    if N > 1 and order != poly.order:
                        terms = poly.as_dict()
                    else:
                        return poly
                else:
                    terms = Poly._permute(poly, *symbols)
            else:
                if any(coeff.has_any_symbols(*symbols) for coeff in poly.coeffs):
                    terms = Poly._decompose(poly.as_basic(), *symbols)
                else:
                    K = len(poly.symbols)

                    if symbols[:K] == poly.symbols:
                        coeffs, T = poly.coeffs, (0,) * (N - K)
                        monoms = tuple(M + T for M in poly.monoms)

                        if order != poly.order:
                            terms = dict(zip(monoms, coeffs))
                    else:
                        terms = Poly._permute(poly, *symbols)
        else:
            terms = Poly._decompose(poly, *symbols)

        if terms:
            f = monomial_cmp(order)

            monoms = terms.keys()
            monoms.sort(f, reverse=True)

            coeffs = [ terms[monom] for monom in monoms ]

        args = (tuple(coeffs), tuple(monoms),
                symbols, order, stamp, None)

        return Basic.__new__(cls, *args, **flags)

    @staticmethod
    def _permute(poly, *symbols):
        terms, N = {}, len(symbols)

        if symbols == poly.symbols[:N]:
            symbols = poly.symbols[N:]

            for coeff, monom in poly.iter_terms():
                coeff *= monomial_as_basic(monom[N:], *symbols)

                monom = monom[:N]

                if terms.has_key(monom):
                    coeff += terms[monom]

                    if not coeff:
                        del terms[monom]
                        continue

                terms[monom] = coeff
        else:
            new_symbols, indices = list(poly.symbols), []

            for s in new_symbols[:]:
                for i, t in enumerate(symbols):
                    if s is t:
                        new_symbols.remove(s)
                        indices.append(i)
                        break
                else:
                    indices.append(None)

            for coeff, monom in poly.iter_terms():
                exponents, j = [0] * N, 0

                for exp, i in zip(monom, indices):
                    if i is None:
                        coeff *= new_symbols[j]**exp
                        j += 1
                    else:
                        exponents[i] = exp

                monom = tuple(exponents)

                if terms.has_key(monom):
                    coeff += terms[monom]

                    if not coeff:
                        del terms[monom]
                        continue

                terms[monom] = coeff

        return terms

    @staticmethod
    def _decompose(poly, *symbols):
        """Converts basic expression to dictionary representation.

           This procedure will expand given expression and scan it,
           extracting coefficients and monomials according to a set
           of symbols, if possible. At this point there is no need
           for specifying ordering information. If conversion is
           not possible an exception is raised.

           This method should be left for internal use. To convert
           expression to a polynomial use Polynomial constructor
           explicitly or Basic.as_poly method.

           >>> from sympy import *
           >>> x, y = symbols('xy')

           >>> Poly._decompose(y*x**2 + 3, x)
           {(2,): y, (0,): 3}

           >>> Poly._decompose(y*x**2 + 3, x, y)
           {(0, 0): 3, (2, 1): 1}

        """
        result, indices, N = {}, {}, len(symbols)

        for i, sym in enumerate(symbols):
            indices[sym] = i

        poly = sympify(poly).expand()

        if poly.is_Add:
            terms = poly.args
        else:
            if poly.is_Number:
                return { (0,) * N : poly }
            else:
                terms = [ poly ]

        for term in terms:
            if not term.has_any_symbols(*symbols):
                coeff, monom = term, (0,) * N
            else:
                if term.is_Mul:
                    factors = term.args
                else:
                    factors = [ term ]

                coeff, monom = S.One, [0] * N

                for factor in factors:
                    if factor.has_any_symbols(*symbols):
                        if factor.is_Pow:
                            if factor.exp.is_Integer:
                                b, e = factor.base, factor.exp.p

                                if b.is_Symbol and e > 0:
                                    monom[indices[b]] += e
                                    continue
                        elif factor.is_Symbol:
                            monom[indices[factor]] += 1
                            continue

                        raise PolynomialError
                    else:
                        coeff *= factor

                monom = tuple(monom)

            if result.has_key(monom):
                coeff += result[monom]

                if not coeff:
                    del result[monom]
                    continue

            result[monom] = coeff

        if not result:
            return { (0,) * N : S.One }
        else:
            return result

    def as_basic(self):
        """Converts polynomial to a valid sympy expression.

           Takes list representation of a polynomial and constructs
           expression using symbols used during creation of a given
           polynomial. If you wish to have different symbols in the
           resulting expressions, use subs() first.

           Note that the result is always returned in expanded form.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           >>> p = Poly(x**2+3, x)
           >>> p.as_basic()
           3 + x**2

        """
        return Add(*[ coeff.as_basic() * monomial_as_basic(monom,
            *self.symbols) for coeff, monom in self.iter_terms() ])

    def as_dict(self):
        """Convert list representation to dictionary representation.

           Due to hashing of immutable expressions in Python, we can
           not store a dictionary directly in a polynomial instance.
           Also it would be inconvenient in case of ordering of
           monomials (unnecessary sorting).

           This method creates dictionary efficiently, so it can be
           used in several algorithms which perform best when dicts
           are being used, eg. addition, multiplication etc.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           >>> p = Poly(x**2+3, x)
           >>> p.as_dict()
           {(2,): 1, (0,): 3}

        """
        return dict(zip(self.monoms, self.coeffs))

    def as_uv_dict(self):
        """Return dictionary representation with integer keys.

           In case of univariate polynomials it is in efficient to
           to handle exponents as singleton tuples, as an example
           see multiplication algorithm. This procedure will
           convert tuples to explicit integers.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           >>> p = Poly(x**2+3, x)
           >>> p.as_uv_dict()
           {0: 3, 2: 1}
        """
        if self.is_univariate:
            return dict(zip([ M[0] for M in self.monoms ], self.coeffs))
        else:
            raise PolynomialError

    @property
    def coeffs(self):
        return self._args[0]

    @property
    def monoms(self):
        return self._args[1]

    @property
    def symbols(self):
        return self._args[2]

    @property
    def order(self):
        return self._args[3]

    @property
    def stamp(self):
        return self._args[4]

    @property
    def domain(self):
        return self._args[5]

    @property
    def args(self):
        return self._args[0:4]

    @property
    def flags(self):
        return { 'order' : self.order }

    @property
    def length(self):
        return len(self.monoms)

    @property
    def degree(self):
        """Returns degree of the leading term. """
        return sum(self.monoms[0])

    @property
    def total_degree(self):
        """Returns true total degree of a polynomial. """
        return max([ sum(monom) for monom in self.monoms ])

    @property
    def norm(self):
        """Computes oo-norm of polynomial's coefficients. """
        return max([ abs(coeff) for coeff in self.coeffs ])

    def iter_coeffs(self):
        for coeff in self.coeffs:
            yield coeff

    def iter_monoms(self):
        for monom in self.monoms:
            yield monom

    def iter_terms(self):
        for coeff, monom in zip(self.coeffs, self.monoms):
            yield coeff, monom

    @property
    def lead_coeff(self):
        return self.coeffs[0]

    @property
    def lead_monom(self):
        return self.monoms[0]

    @property
    def lead_term(self):
        return (self.coeffs[0], self.monoms[0])

    LC = lead_coeff
    LM = lead_monom
    LT = lead_term

    def __abs__(self):
        return self.__class__(([ abs(coeff) for coeff in self.coeffs ],
            self.monoms), *self.symbols, **self.flags)

    def __neg__(self):
        return self.__class__(([ -coeff for coeff in self.coeffs ],
            self.monoms), *self.symbols, **self.flags)

    def __add__(self, other):
        try:
            self, poly = self.unify_with(other)
        except PolynomialError:
            return self.as_basic() + other.as_basic()

        if poly.is_zero:
            return self

        if self.is_zero:
            return poly

        if poly.is_monomial:
            return self.add_term(*poly.LT)

        if self.is_monomial:
            return poly.add_term(*self.LT)

        terms = self.as_dict()

        for coeff, monom in poly.iter_terms():
            if terms.has_key(monom):
                coeff += terms[monom]

                if not coeff:
                    del terms[monom]
                    continue

            terms[monom] = coeff

        return self.__class__(terms, *self.symbols, **self.flags)

    def __sub__(self, other):
        try:
            self, poly = self.unify_with(other)
        except PolynomialError:
            return self.as_basic() - other.as_basic()

        if poly.is_zero:
            return self

        if self.is_zero:
            return -poly

        if poly.is_monomial:
            return self.sub_term(*poly.LT)

        if self.is_monomial:
            return (-poly).add_term(*self.LT)

        terms = self.as_dict()

        for coeff, monom in poly.iter_terms():
            if terms.has_key(monom):
                coeff -= terms[monom]

                if not coeff:
                    del terms[monom]
                    continue

            terms[monom] = -coeff

        return self.__class__(terms, *self.symbols, **self.flags)

    def __mul__(self, other):
        """Efficiently multiply sparse and dense polynomials.

           Given polynomials P and Q, if both of them are dense, then
           in univariate case perform dense multiplication, otherwise
           apply Kronecker 'trick', mapping multivariate polynomials
           to univariate ones in last variable and then multiply.

           If any of the polynomials is sparse then in both univariate
           and multivariate cases use naive multiplication algorithm.

           For more information on implemented algorithms refer to:

           [1] R. T. Moenck, Practical Fast Polynomial Multiplication,
               Proceedings of the third ACM symposium on Symbolic and
               algebraic computation, ACM Press, Yorktown Heights,
               New York, USA, 1976, pp. 136-148
        """
        try:
            self, poly = self.unify_with(other)
        except PolynomialError:
            return self.as_basic() * other.as_basic()

        if self.is_constant:
            if self.is_zero:
                return self
            elif self.is_one:
                return poly
            else:
                LC = self.lead_coeff

                coeffs = [ LC * coeff for coeff in poly.coeffs ]

                for i, coeff in enumerate(coeffs):
                    if not coeff.is_Atom:
                        coeffs[i] = cancel(coeff)

                return poly.__class__((coeffs, poly.monoms),
                    *poly.symbols, **poly.flags)

        if poly.is_constant:
            if poly.is_zero:
                return poly
            elif poly.is_one:
                return self
            else:
                LC = poly.lead_coeff

                coeffs = [ coeff * LC for coeff in self.coeffs ]

                for i, coeff in enumerate(coeffs):
                    if not coeff.is_Atom:
                        coeffs[i] = cancel(coeff)

                return self.__class__((coeffs, self.monoms),
                    *self.symbols, **self.flags)

        if self.is_monomial:
            LC, LM = self.lead_term

            coeffs = [ LC * coeff for coeff in poly.coeffs ]
            monoms = [ monomial_mul(LM, monom) for monom in poly.monoms ]

            for i, coeff in enumerate(coeffs):
                if not coeff.is_Atom:
                    coeffs[i] = cancel(coeff)

            return poly.__class__((coeffs, monoms), *poly.symbols, **poly.flags)

        if poly.is_monomial:
            LC, LM = poly.lead_term

            coeffs = [ coeff * LC for coeff in self.coeffs ]
            monoms = [ monomial_mul(monom, LM) for monom in self.monoms ]

            for i, coeff in enumerate(coeffs):
                if not coeff.is_Atom:
                    coeffs[i] = cancel(coeff)

            return self.__class__((coeffs, monoms), *self.symbols, **self.flags)

        if self.is_dense and poly.is_dense:
            if self.is_multivariate:
                a = monomial_max(*self.monoms)
                b = monomial_max(*poly.monoms)

                degs, p, q = [1], {}, {}

                for x, y in reversed(zip(a, b)[1:]):
                    degs.insert(0, degs[0]*(x+y+1))

                N = sum([ x*y for x, y in zip(self.LM, degs) ])
                M = sum([ x*y for x, y in zip(poly.LM, degs) ])

                for coeff, monom in self.iter_terms():
                    p[sum([ x*y for x, y in zip(monom, degs) ])] = coeff

                for coeff, monom in poly.iter_terms():
                    q[sum([ x*y for x, y in zip(monom, degs) ])] = coeff
            else:
                p, N = self.as_uv_dict(), self.degree
                q, M = poly.as_uv_dict(), poly.degree

            coeffs, monoms = [], []

            for k in xrange(N+M, -1, -1):
                coeff = 0

                for i in xrange(k+1):
                    if p.has_key(i) and q.has_key(k-i):
                        product = p[i] * q[k-i]

                        if product.is_Atom:
                            coeff += product
                        else:
                            coeff += cancel(product)

                if coeff:
                    coeffs.append(coeff)
                    monoms.append((k,))

            if self.is_multivariate:
                terms, degs = {}, degs[:-1]

                for i, d in enumerate(monoms):
                    monom, d = [], d[0]

                    for j in degs:
                        k, d = divmod(d, j)
                        monom.append(k)

                    terms[tuple(monom)+(d,)] = coeffs[i]
            else:
                terms = coeffs, monoms
        else:
            terms = {}

            for coeff_p, M in self.iter_terms():
                for coeff_q, N in poly.iter_terms():
                    monom = monomial_mul(M, N)

                    coeff = coeff_p * coeff_q

                    if not coeff.is_Atom:
                        coeff = cancel(coeff)

                    if terms.has_key(monom):
                        coeff += terms[monom]

                        if not coeff:
                            del terms[monom]
                            continue

                    terms[monom] = coeff

        return self.__class__(terms, *self.symbols, **self.flags)

    def __pow__(self, other):
        """Polynomial exponentiation using binary method.

           Given a polynomial P and integer exponent N, raise P to power
           N in floor(lg(N)) + 1(N) multiplications,  where lg(N) stands
           for binary logarithm and 1(N) is the number of ones in binary
           representation of N.

           For more information on the implemented algorithm refer to:

           [1] D. E. Knuth, The Art of Computer Programming: Seminumerical
               Algorithms, v.2, Addison-Wesley Professional, 1997, pp. 461

        """
        other = sympify(other)

        if isinstance(other, Poly):
            if other.is_constant:
                other = sympify(other.lead_coeff)
            else:
                return self.as_basic()**other.as_basic()

        if other.is_Integer:
            if other is S.One:
                return self

            P = self.__class__(S.One, *self.symbols, **self.flags)

            if other is S.Zero:
                return P

            N, Q = abs(int(other)), self

            while True:
                N, M = N/2, N

                if M & 1:
                    P *= Q

                    if N == 0:
                        break

                Q *= Q

            if other.is_positive:
                return P
            else:
                return Pow(P, S.NegativeOne)
        else:
            return self.as_basic()**other

    def __div__(self, other):
        try:
            return sympy.polys.algorithms.poly_div(self, other)[0]
        except PolynomialError:
            return self.as_basic() / other.as_basic()

    def __mod__(self, other):
        try:
            return sympy.polys.algorithms.poly_div(self, other)[1]
        except PolynomialError:
            return S.Zero

    def __divmod__(self, other):
        try:
            return sympy.polys.algorithms.poly_div(self, other)
        except PolynomialError:
            return (self.as_basic() / other.as_basic(), S.Zero)

    __truediv__ = __div__

    @property
    def is_zero(self):
        return self.coeffs in ((S.Zero,), (0,))

    @property
    def is_one(self):
        return self.coeffs in ((S.One,), (1,)) and \
            all(e == 0 for e in self.monoms[0])

    @property
    def is_constant(self):
        return len(self.monoms) == 1 and \
            all(e == 0 for e in self.monoms[0])

    @property
    def is_monomial(self):
        return len(self.monoms) == 1

    @property
    def is_univariate(self):
        return len(self.symbols) == 1

    @property
    def is_multivariate(self):
        return len(self.symbols) != 1

    @property
    def is_homogeneous(self):
        return any(e != 0 for e in self.monoms[-1])

    @property
    def is_inhomogeneous(self):
        return all(e == 0 for e in self.monoms[-1])

    @property
    def is_sparse(self):
        return not self.is_dense

    @property
    def is_dense(self):
        """Returns True if 'self' is dense.

           Let 'self' be a polynomial in M variables of a total degree N
           and having L terms (with non-zero coefficients). Let K be the
           number of monomials in M variables of degree at most N.  Then
           'self' is considered dense if it's at least 90% filled.

           The total number of monomials is given by (M + N)! / (M! N!),
           where the factorials are estimated using improved Stirling's
           approximation:

                       n! = sqrt((2 n + 1/3) pi) n**n exp(-n)

           For more information on this subject refer to:

             http://mathworld.wolfram.com/StirlingsApproximation.html

        """
        def enum(M, N):
            U = float(M+N)
            V = (6*M+1)*(6*N+1)
            S = 2.4*math.sqrt(U/V)
            A = math.pow(U/M, M)
            B = math.pow(U/N, N)
            return S * A * B

        V, N = len(self.symbols), self.degree

        return (self.length / enum(V, N)) > 0.9

    @property
    def is_primitive(self):
        return self.content in (S.One, 1)

    @property
    def is_monic(self):
        return self.lead_coeff in (S.One, 1)

    @property
    def has_integer_coeffs(self):
        return self.domain == 'Z'

    @property
    def has_rational_coeffs(self):
        return self.domain == 'Q'

    @property
    def has_radical_coeffs(self):
        return self.domain == 'R'

    @property
    def has_complex_coeffs(self):
        return self.domain == 'C'

    @property
    def has_symbolic_coeffs(self):
        return self.domain == 'S'

    def as_monic(self):
        """Returns leading coefficient and monic polynomial.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           >>> Poly(x**2 + 4, x).as_monic()
           Poly((1, 4), ((2,), (0,)), (x,), 'grlex')

           >>> Poly(2*x**2 + 4, x).as_monic()
           Poly((1, 2), ((2,), (0,)), (x,), 'grlex')

           >>> Poly(y*x**2 + (y**2+y), x).as_monic()
           Poly((1, 1 + y), ((2,), (0,)), (x,), 'grlex')

        """
        LC = self.lead_coeff

        coeffs = [ coeff / LC for coeff in self.coeffs ]

        for i, coeff in enumerate(coeffs):
            if not coeff.is_Atom:
                coeffs[i] = cancel(coeff)

        return self.__class__((coeffs, self.monoms),
            *self.symbols, **self.flags)

    @property
    def content(self):
        """Returns GCD of all the coefficients.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           # TBD : needs poly_gcd / func_gcd

        """
        raise NotImplementedError

    def as_primitive(self):
        """Returns content and primitive part of a polynomial.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           # TBD : needs content

        """
        content = self.content

        if content is S.One:
            return S.One, self
        else:
            if content.is_number:
                coeffs = [ coeff / content for coeff in self.coeffs ]
            else:
                from sympy.simplify import cancel # avoid recursive import
                coeffs = [ cancel(coeff / content) for coeff in self.coeffs ]

            return content, self.__class__((coeffs,
                self.monoms), *self.symbols, **self.flags)

    def map_coeffs(self, f, *args, **kwargs):
        """Apply a function to all the coefficients.

           >>> from sympy import *
           >>> x,y,u,v = symbols('xyuv')

           >>> p = Poly(x**2 + 2*x*y, x, y)
           >>> q = p.map_coeffs(lambda c: 2*c)

           >>> q.as_basic()
           4*x*y + 2*x**2

           >>> p = Poly(u*x**2 + v*x*y, x, y)
           >>> q = p.map_coeffs(expand, complex=True)

           >>> q.as_basic()
           x**2*(I*im(u) + re(u)) + x*y*(I*im(v) + re(v))

        """
        terms = []

        for coeff, monom in self.iter_terms():
            coeff = f(coeff, *args, **kwargs)

            if coeff.has_any_symbols(*self.symbols):
                raise PolynomialError
            elif coeff is not S.Zero:
                terms.append((coeff, monom))

        return self.__class__(terms, *self.symbols, **self.flags)

    def coeff(self, *monom):
        """Returns coefficient of a particular monomial.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           >>> p = Poly(3*x**2*y + 4*x*y**2 + 1, x, y)

           >>> p.coeff(2, 1)
           3
           >>> p.coeff(1, 2)
           4
           >>> p.coeff(1, 1)
           0

           If len(monom) == 0 then returns coeff of the constant term:

           >>> p.coeff(0, 0)
           1
           >>> p.coeff()
           1

        """
        if not monom:
            if all(e == 0 for e in self.monoms[-1]):
                return self.coeffs[-1]
        else:
            for i in xrange(len(self.monoms)):
                if self.monoms[i] == monom:
                    return self.coeffs[i]

        return S.Zero

    def unify_with(self, other):
        """Unify 'self' with a polynomial or a set of polynomials.

           This method will return polynomials of the same type,  dominated
           by 'self', with a common set of symbols (which is a union of all
           symbols from all polynomials) and with common monomial ordering.

           You can pass a polynomial  or an expression to this method, or
           a list or a tuple of polynomials or expressions. If any of the
           inputs would be an expression then it will be converted to a
           polynomial.

        """
        symbols, stamp = self.symbols, self.stamp
        flags, cls = self.flags, self.__class__

        if isinstance(other, (tuple, list)):
            for poly in other:
                if isinstance(poly, Poly):
                    stamp |= poly.stamp
                #elif atoms:
                #    stamp |= poly.atoms(Symbol)

            if not (stamp <= self.stamp):
                symbols = tuple(sorted(stamp))
                self = cls(self, *symbols, **flags)

            other = other.__class__( cls(poly,
                *symbols, **flags) for poly in other )
        else:
            other = sympify(other)

            if isinstance(other, Poly):
                stamp |= other.stamp
            #elif atoms:
            #    stamp |= other.atoms(Symbol)

            if not (stamp <= self.stamp):
                symbols = tuple(sorted(stamp))
                self = cls(self, *symbols, **flags)

            other = cls(other, *symbols, **flags)

        return self, other

    def diff(self, *symbols):
        """Efficiently differentiate polynomials.

           Differentiate a polynomial with respect to a set of symbols.  If
           a symbol is polynomial's variable, then monomial differentiation
           is performed and coefficients updated with integer factors. In
           other case each of the coefficients is differentiated.

           Additionally, for each of the symbols you can specify a single
           positive integer which will indicate the number of times to
           perform differentiation using this symbol.

           >>> from sympy import *
           >>> x,y,z = symbols('xyz')

           >>> p = Poly(x**2*y + z**2, x, y)
           >>> print p
           Poly((1, z**2), ((2, 1), (0, 0)), (x, y), 'grlex')

           >>> p.diff(x)
           Poly((2,), ((1, 1),), (x, y), 'grlex')

           >>> p.diff(x, 2)
           Poly((2,), ((0, 1),), (x, y), 'grlex')

           >>> p.diff(x, 2, y)
           Poly((2,), ((0, 0),), (x, y), 'grlex')

           >>> p.diff(z)
           Poly((2*z,), ((0, 0),), (x, y), 'grlex')

        """
        if self.is_zero:
            return self

        new_symbols = []

        for s in symbols:
            s = sympify(s)

            if s.is_Symbol:
                new_symbols.append((s, 1))
            elif s.is_Integer:
                sym, _ = new_symbols.pop()
                new_symbols.append((sym, int(s)))
            else:
                raise TypeError

        indices, symbols = {}, self.stamp

        for i, s in enumerate(self.symbols):
            indices[s] = i

        poly = self.as_dict()

        for s, k in new_symbols:
            new_poly = {}

            if s in symbols:
                i = indices[s]

                for M, coeff in poly.iteritems():
                    n = M[i] - k

                    if n >= 0:
                        monom = M[:i]+(n,)+M[i+1:]

                        for j in xrange(n, M[i]):
                            coeff *= j+1

                        if new_poly.has_key(monom):
                            coeff += new_poly[monom]

                            if not coeff:
                                del new_poly[monom]
                                continue

                        new_poly[monom] = coeff
            elif not isinstance(self, IntegerPoly):
                for monom, coeff in poly.iteritems():
                    if coeff.has_any_symbols(s):
                        coeff = coeff.diff(*([s]*k))

                        if coeff:
                            new_poly[monom] = coeff

            poly = new_poly

            if not poly:
                break

        return self.__class__(poly, *self.symbols, **self.flags)

    def integrate(self, *symbols):
        """Efficiently integrate polynomials.

           Integrate a polynomial with respect a set of symbols. If a
           symbol is polynomial's variable, then monomial integration
           is performed and coefficients updated with integer factors.
           In other case each of the coefficients is integrated.

           Additionally, for each of the symbols you can specify a
           single positive integer which will indicate the number
           of times to perform integration using this symbol.

           >>> from sympy import *
           >>> x,y,z = symbols('xyz')

           >>> p = Poly(x**2*y + z**2, x, y)
           >>> print p
           Poly((1, z**2), ((2, 1), (0, 0)), (x, y), 'grlex')

           >>> p.integrate(x)
           Poly((1/3, z**2), ((3, 1), (1, 0)), (x, y), 'grlex')

           >>> p.integrate(x, 2)
           Poly((1/12, (1/2)*z**2), ((4, 1), (2, 0)), (x, y), 'grlex')

           >>> p.integrate(x, 2, y)
           Poly((1/24, (1/2)*z**2), ((4, 2), (2, 1)), (x, y), 'grlex')

           >>> p.integrate(z)
           Poly((z, (1/3)*z**3), ((2, 1), (0, 0)), (x, y), 'grlex')

        """
        if self.is_zero:
            return self

        new_symbols = []

        for s in symbols:
            s = sympify(s)

            if s.is_Symbol:
                new_symbols.append((s, 1))
            elif s.is_Integer:
                sym, _ = new_symbols.pop()
                new_symbols.append((sym, int(s)))
            else:
                raise TypeError

        indices, symbols = {}, self.stamp

        for i, s in enumerate(self.symbols):
            indices[s] = i

        poly = self.as_dict()

        for s, k in new_symbols:
            new_poly = {}

            if s in symbols:
                i = indices[s]

                for M, coeff in poly.iteritems():
                    n = M[i] + k

                    monom = M[:i]+(n,)+M[i+1:]

                    for j in xrange(M[i], n):
                        coeff /= j+1

                    if new_poly.has_key(monom):
                        coeff += new_poly[monom]

                        if not coeff:
                            del new_poly[monom]
                            continue

                    new_poly[monom] = coeff
            else:
                for M, coeff in poly.iteritems():
                    new_poly[M] = C.Integral(coeff, *([s]*k)).doit()

            if not new_poly:
                break
            else:
                poly = new_poly

        return self.__class__(poly, *self.symbols, **self.flags)

    def add_term(self, coeff, monom):
        """Efficiently add a single term to 'self'.

           The list of monomials is sorted at initialization time, this
           motivates usage of binary search algorithm to find an index
           of an existing monomial or a suitable place for a new one.
           This gives O(lg(n)) complexity, where 'n' is the initial
           number of terms, superior to naive approach.

           For more information on the implemented algorithm refer to:

           [1] D. E. Knuth, The Art of Computer Programming: Sorting
               and Searching, v.1, Addison-Wesley Professional, 1998

        """
        if self.is_zero:
            coeffs = (coeff,)
            monoms = (monom,)
        else:
            coeffs = list(self.coeffs)
            monoms = list(self.monoms)

            compare = monomial_cmp(self.order)

            if compare(monom, monoms[0]) > 0:
                coeffs.insert(0, coeff)
                monoms.insert(0, monom)
            elif compare(monom, monoms[-1]) < 0:
                coeffs.append(coeff)
                monoms.append(monom)
            else:
                lo, hi = 0, len(monoms)-1

                while lo <= hi:
                    i = (lo + hi) // 2

                    k = compare(monom, monoms[i])

                    if not k:
                        coeff += coeffs[i]

                        if coeff:
                            coeffs[i] = coeff
                        else:
                            del coeffs[i]
                            del monoms[i]

                        break
                    else:
                        if k > 0:
                            hi = i - 1
                        else:
                            lo = i + 1
                else:
                    coeffs.insert(i, coeff)
                    monoms.insert(i, monom)

        return self.__class__((coeffs, monoms),
            *self.symbols, **self.flags)

    def sub_term(self, coeff, monom):
        """Efficiently subtract a single term from 'self'.

           The list of monomials is sorted at initialization time, this
           motivates usage of binary search algorithm to find an index
           of an existing monomial or a suitable place for a new one.
           This gives O(lg(n)) complexity, where 'n' is the initial
           number of terms, superior to naive approach.

           For more information on the implemented algorithm refer to:

           [1] D. E. Knuth, The Art of Computer Programming: Sorting
               and Searching, v.2, Addison-Wesley Professional, 1998

        """
        if self.is_zero:
            coeffs = (-coeff,)
            monoms = (monom,)
        else:
            coeffs = list(self.coeffs)
            monoms = list(self.monoms)

            compare = monomial_cmp(self.order)

            if compare(monom, monoms[0]) > 0:
                coeffs.insert(0, -coeff)
                monoms.insert(0, monom)
            elif compare(monom, monoms[-1]) < 0:
                coeffs.append(-coeff)
                monoms.append(monom)
            else:
                lo, hi = 0, len(monoms)-1

                while lo <= hi:
                    i = (lo + hi) // 2

                    k = compare(monom, monoms[i])

                    if not k:
                        coeff -= coeffs[i]

                        if coeff:
                            coeffs[i] = coeff
                        else:
                            del coeffs[i]
                            del monoms[i]

                        break
                    else:
                        if k > 0:
                            hi = i - 1
                        else:
                            lo = i + 1
                else:
                    coeffs.insert(i, -coeff)
                    monoms.insert(i, monom)

        return self.__class__((coeffs, monoms),
            *self.symbols, **self.flags)

    def kill_lead_term(self):
        """Removes leading term from 'self'. """
        terms = self.coeffs[1:], self.monoms[1:]
        return self.__class__(terms, *self.symbols, **self.flags)

    def kill_last_term(self):
        """Removes last term from 'self'. """
        terms = self.coeffs[:-1], self.monoms[:-1]
        return self.__class__(terms, *self.symbols, **self.flags)

    def __call__(self, *point):
        """Efficiently evaluate polynomial at a given point.

           Evaluation is always done using Horner scheme.  In multivariate
           case a greedy algorithm is used to obtain a sequence of partial
           evaluations which minimizes the total number of multiplications
           required to perform this evaluation. This strategy is efficient
           for most of multivariate polynomials.

           Note that evaluation is done for all variables, which means the
           dimension of the given point must match the number of symbols.

           If you wish to efficiently evaluate polynomial for a subset of
           symbols use 'evaluate' method instead. Alternatively one can
           use Basic.subs() for this purpose.

           >>> from sympy import *
           >>> x,y = symbols('xy')

           >>> p = Poly(x**2 + 2*x + 1, x)

           >>> p(2)
           9
           >>> p(y)
           1 + y*(2 + y)

           For more information on the implemented algorithm refer to:

           [1] M. Ceberio, V. Kreinovich, Greedy Algorithms for Optimizing
               Multivariate Horner Schemes, ACM SIGSAM Bulletin, Volume 38,
               Issue 1, 2004, pp. 8-15

        """
        N = len(self.symbols)

        if len(point) != N:
            raise ValueError

        if self.is_univariate:
            terms = self.as_uv_dict()

            point, result = point[0], 0

            for k in xrange(self.degree, -1, -1):
                result *= point

                if terms.has_key(k):
                    result += terms[k]

            return result
        else:
            def evaluate(terms):
                count = [0] * N

                for monom in terms.iterkeys():
                    for i, M in enumerate(monom):
                        if M != 0:
                            count[i] += 1

                K = max(count)

                if K <= 1:
                    result = 0

                    for monom, coeff in terms.iteritems():
                        for base, exp in zip(point, monom):
                            if exp != 0:
                                if exp == 1:
                                    coeff *= base
                                else:
                                    coeff *= base**exp

                        result += coeff

                    return result
                else:
                    k, indeps, depend = count.index(K), {}, {}

                    n = min([ M[k] for M in terms.iterkeys() if M[k] ])

                    for M, coeff in terms.iteritems():
                        if M[k] != 0:
                            depend[M[:k]+(M[k]-n,)+M[k+1:]] = coeff
                        else:
                            indeps[M] = coeff

                    result = point[k]**n * evaluate(depend)

                    if indeps:
                        return result + evaluate(indeps)
                    else:
                        return result

            return evaluate(self.as_dict())

    def evaluate(self, pattern):
        """Evaluates polynomial for a given set of symbols. """
        symbols = list(self.symbols)

        if type(pattern) is dict:
            pattern = pattern.items()
        elif type(pattern) is tuple:
            pattern = [pattern]

        poly = self.as_dict()

        for s, value in pattern:
            if s not in self.stamp:
                raise PolynomialError
            else:
                i = symbols.index(s)

            # 'value' might be int | long
            if isinstance(value, Symbol):
                if value in self.stamp:
                    raise PolynomialError

            terms = {}

            for M, coeff in poly.iteritems():
                monom = M[:i] + M[i+1:]
                coeff *= value ** M[i]

                if terms.has_key(monom):
                    coeff += terms[monom]

                    if not coeff:
                        del terms[monom]
                        continue

                terms[monom] = coeff

            del symbols[i]
            poly = terms

        if len(poly) == 1:
            return poly.popitem()[1]
        else:
            return self.__class__(terms,
                *symbols, **self.flags)

    def _eval_subs(self, old, new):
        symbols = list(self.symbols)

        if old in self.stamp:
            terms, i = {}, symbols.index(old)

            if new.is_Symbol:
                if new in self.stamp:
                    j = symbols.index(new)

                    for coeff, M in self.iter_terms():
                        n, m = M[i], M[j]

                        if i < j:
                            monom = M[:i]+M[i+1:j]+(m+n,)+M[j+1:]
                        else:
                            monom = M[:j]+(m+n,)+M[j+1:i]+M[i+1:]

                        if terms.has_key(monom):
                            coeff += terms[monom]

                            if not coeff:
                                del terms[monom]
                                continue

                        terms[monom] = coeff

                    del symbols[i]

                    return self.__class__(terms, *symbols, **self.flags)
                else:
                    for coeff in self.coeffs:
                        if coeff.has_any_symbols(new):
                            break
                    else:
                        symbols[i], terms = new, (self.coeffs, self.monoms)
                        return self.__class__(terms, *symbols, **self.flags)
            elif new.is_number:
                if len(symbols) == 1:
                    return self(new)
                else:
                    return self.evaluate((old, new))
        elif not new.has_any_symbols(*symbols):
            coeffs = [ sympify(coeff).subs(old, new) for coeff in self.coeffs ]
            return self.__class__((coeffs, self.monoms), *symbols, **self.flags)

        result = self.as_basic().subs(old, new)

        try:
            return self.__class__(result, *symbols, **self.flags)
        except PolynomialError:
            return result

    def __eq__(self, other):
        """Compare polynomials up to order of symbols and monomials. """
        try:
            poly = self.__class__(other, *self.symbols, **self.flags)
        except PolynomialError:
            return False

        if self.length != poly.length:
            return False

        if hash(self.monoms) != hash(poly.monoms):
            return False

        if hash(self.coeffs) != hash(poly.coeffs):
            for a, b in zip(self.coeffs, poly.coeffs):
                if a != b:
                    return False

        return True

    def __ne__(self, other):
        """Compare polynomials up to order of symbols and monomials. """
        try:
            poly = self.__class__(other, *self.symbols, **self.flags)
        except PolynomialError:
            return True

        if self.length != poly.length:
            return True

        if hash(self.monoms) != hash(poly.monoms):
            return True

        if hash(self.coeffs) != hash(poly.coeffs):
            for a, b in zip(self.coeffs, poly.coeffs):
                if a != b:
                    return True

        return False

    def __nonzero__(self):
        return self.coeffs not in ((S.Zero,), (0,))

    def _eval_is_polynomial(self, symbols):
        try:
            self.__class__(self, *symbols, **self.flags)
        except PolynomialError:
            return False

        return True

class IntegerPoly(Poly):
    pass