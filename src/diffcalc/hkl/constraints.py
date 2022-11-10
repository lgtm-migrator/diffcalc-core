"""Module handling constraint information for diffractometer calculations."""
import dataclasses
from enum import Enum
from itertools import zip_longest
from typing import Collection, Dict, List, Literal, Optional, Tuple, Union

from diffcalc.util import DiffcalcException, unit, ureg
from pint import Quantity

_con_category = Enum("_con_category", "DETECTOR REFERENCE SAMPLE")
_con_type = Enum("_con_type", "VALUE VOID")


@dataclasses.dataclass(eq=False)
class _Constraint:
    name: str
    _category: _con_category
    _type: _con_type
    value: Optional[Union[Quantity, Literal["True"]]] = None

    @property
    def active(self) -> bool:
        return self.value is not None


class Constraints:
    """Collection of angle constraints for diffractometer calculations.

    Three constraints are required for calculations of miller indices and
    the corresponding diffractometer positions. Allowed configurations include
    at most one of the reference and the detector type constraint and up to
    three of the sample type constraints.

    List of the available constraint combinations:

        1 x samp, 1 x ref and 1 x det:  all

        2 x samp and 1 x ref:  chi & phi
                               chi & eta
                               chi & mu
                               mu & eta
                               mu & phi
                               eta & phi

        2 x samp and 1 x det:  chi & phi
                               mu & eta
                               mu & phi
                               mu & chi
                               eta & phi
                               eta & chi
                               bisect & mu
                               bisect & eta
                               bisect & omega

        3 x samp:              eta, chi & phi
                               mu, chi & phi
                               mu, eta & phi
                               mu, eta & chi
    """

    def __init__(
        self,
        constraints: Collection[Union[Tuple[str, float], str]] = None,
        indegrees: bool = True,
    ):
        """Object for setting diffractometer angle constraints."""
        self._delta = _Constraint("delta", _con_category.DETECTOR, _con_type.VALUE)
        self._nu = _Constraint("nu", _con_category.DETECTOR, _con_type.VALUE)
        self._qaz = _Constraint("qaz", _con_category.DETECTOR, _con_type.VALUE)
        self._naz = _Constraint("naz", _con_category.DETECTOR, _con_type.VALUE)

        self._a_eq_b = _Constraint("a_eq_b", _con_category.REFERENCE, _con_type.VOID)
        self._alpha = _Constraint("alpha", _con_category.REFERENCE, _con_type.VALUE)
        self._beta = _Constraint("beta", _con_category.REFERENCE, _con_type.VALUE)
        self._psi = _Constraint("psi", _con_category.REFERENCE, _con_type.VALUE)
        self._bin_eq_bout = _Constraint(
            "bin_eq_bout", _con_category.REFERENCE, _con_type.VOID
        )
        self._betain = _Constraint("betain", _con_category.REFERENCE, _con_type.VALUE)
        self._betaout = _Constraint("betaout", _con_category.REFERENCE, _con_type.VALUE)

        self._mu = _Constraint("mu", _con_category.SAMPLE, _con_type.VALUE)
        self._eta = _Constraint("eta", _con_category.SAMPLE, _con_type.VALUE)
        self._chi = _Constraint("chi", _con_category.SAMPLE, _con_type.VALUE)
        self._phi = _Constraint("phi", _con_category.SAMPLE, _con_type.VALUE)
        self._bisect = _Constraint("bisect", _con_category.SAMPLE, _con_type.VOID)
        self._omega = _Constraint("omega", _con_category.SAMPLE, _con_type.VALUE)

        self._all: Tuple[_Constraint, ...] = (
            self._delta,
            self._nu,
            self._qaz,
            self._naz,
            self._a_eq_b,
            self._alpha,
            self._beta,
            self._psi,
            self._bin_eq_bout,
            self._betain,
            self._betaout,
            self._mu,
            self._eta,
            self._chi,
            self._phi,
            self._bisect,
            self._omega,
        )
        self.indegrees = indegrees
        if constraints is not None:
            if isinstance(constraints, dict):
                self.asdict = constraints
            elif isinstance(constraints, tuple):
                self.astuple = constraints
            elif isinstance(constraints, (list, set)):
                self.astuple = tuple(constraints)
            else:
                raise DiffcalcException(
                    f"Invalid constraint parameter type: {type(constraints)}"
                )

    def __str__(self) -> str:
        """Output text representation of active constraint set.

        Returns
        -------
        str
            Table representation of the available constraints with a list of
            constrained angle names and values.
        """
        lines = []
        lines.extend(self._build_display_table_lines())
        lines.append("")
        lines.extend(self._report_constraints_lines())
        lines.append("")
        if self.is_fully_constrained() and not self.is_current_mode_implemented():
            lines.append("    Sorry, this constraint combination is not implemented.")
        return "\n".join(lines)

    @property
    def constrained(self):
        return tuple(con for con in self._all if con.active)

    @property
    def detector(self) -> Dict[str, Union[float, Literal["True"]]]:
        return {
            con.name: con.value
            for con in self._all
            if con.active and con._category is _con_category.DETECTOR
        }

    @property
    def reference(self) -> Dict[str, Union[float, Literal["True"]]]:
        return {
            con.name: con.value
            for con in self._all
            if con.active and con._category is _con_category.REFERENCE
        }

    @property
    def sample(self) -> Dict[str, Union[float, Literal["True"]]]:
        return {
            con.name: con.value
            for con in self._all
            if con.active and con._category is _con_category.SAMPLE
        }

    @property
    def all(self) -> Dict[str, Union[float, bool, None]]:
        """Get all angle names and values.

        Returns
        -------
        Dict[str, Union[float, bool, None]]
            Dictionary with all angle names and values.
        """
        return {con.name: getattr(self, con.name) for con in self._all}

    @property
    def asdict(self) -> Dict[str, Union[float, bool]]:
        """Get all constrained angle names and values.

        Returns
        -------
        Dict[str, Union[float, bool]]
            Dictionary with all constrained angle names and values.
        """
        return {con.name: getattr(self, con.name) for con in self._all if con.active}

    @asdict.setter
    def asdict(self, constraints):
        assert isinstance(constraints, dict)  # TODO: get rid of this line
        self.clear()
        if constraints is None:
            return
        for con_name, con_value in constraints.items():
            if hasattr(self, con_name) and isinstance(
                getattr(self, "_" + con_name), _Constraint
            ):
                setattr(self, con_name, con_value)
            else:
                raise DiffcalcException(f"Invalid constraint name: {con_name}")

    @property
    def astuple(self) -> Tuple[Union[Tuple[str, float], str], ...]:
        """Get all constrained angle names and values.

        Returns
        -------
        Tuple[Union[Tuple[str, float], str], ...]
            Tuple with all constrained angle names and values.
        """
        res = []
        for con in self.constrained:
            if con._type is _con_type.VALUE:
                res.append((con.name, getattr(self, con.name)))
            elif con._type is _con_type.VOID:
                res.append(con.name)
            else:
                raise DiffcalcException(
                    f"Invalid {con.name} constraint type found: {type(con._type)}"
                )
        return tuple(res)

    @astuple.setter
    def astuple(self, constraints: Tuple[Union[Tuple[str, float], str], ...]) -> None:
        assert isinstance(constraints, tuple)
        self.clear()
        if constraints is None:
            return
        for el in constraints:
            if (
                isinstance(el, str)
                and hasattr(self, el)
                and isinstance(getattr(self, "_" + el), _Constraint)
            ):
                setattr(self, el, True)
            elif (
                isinstance(el, (type(("a", 1)), type(("a", 1.0))))
                and hasattr(self, el[0])
                and isinstance(getattr(self, "_" + el[0]), _Constraint)
            ):
                setattr(self, *el)
            else:
                raise DiffcalcException(f"Invalid constraint parameter: {el}")

    def _set_factory(
        self, con: _Constraint, value: Optional[Union[float, Quantity, Literal["True"]]]
    ) -> None:
        def set_value(val: Optional[Union[float, Quantity, Literal["True"]]]) -> None:
            if con._type == _con_type.VALUE:
                if val is True:
                    raise DiffcalcException(
                        f"Constraint {con.name} requires numerical value. "
                        'Found "True" instead.'
                    )
            if isinstance(val, Quantity):
                con.value = val.to(unit)
            else:
                con.value = float(val) * ureg(unit)

            if con._type == _con_type.VOID:
                if ((val) is not None) and (val is not True):
                    raise DiffcalcException(
                        f"Constraint {con.name} requires boolean value. "
                        f"Found {type(val)} instead."
                    )
                con.value = val

        cons_of_this_category = {
            c for c in self.constrained if c._category is con._category
        }
        can_set_constraint_of_this_category = (
            not self.is_fully_constrained(con) and not self.is_fully_constrained()
        )

        if not can_set_constraint_of_this_category:
            if len(cons_of_this_category) == 1:
                existing_con = cons_of_this_category.pop()
                existing_con.value = None
            else:
                raise DiffcalcException(
                    f"Cannot set {con.name} constraint. First un-constrain one of the\n"
                    f"angles {', '.join(sorted(c.name for c in self.constrained))}."
                )

        set_value(value)

    @property
    def delta(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for delta angle."""
        return self._delta.value

    @delta.setter
    def delta(self, val) -> None:
        self._set_factory(self._delta, val)

    @delta.deleter
    def delta(self):
        self._delta.value = None

    @property
    def nu(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for nu angle."""
        return self._nu.value

    @nu.setter
    def nu(self, val):
        self._set_factory(self._nu, val)

    @nu.deleter
    def nu(self):
        self._nu.value = None

    @property
    def qaz(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for qaz angle."""
        return self._qaz.value

    @qaz.setter
    def qaz(self, val):
        self._set_factory(self._qaz, val)

    @qaz.deleter
    def qaz(self):
        self._qaz.value = None

    @property
    def naz(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for naz angle."""
        return self._naz.value

    @naz.setter
    def naz(self, val):
        self._set_factory(self._naz, val)

    @naz.deleter
    def naz(self):
        self._naz.value = None

    @property
    def a_eq_b(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for setting alpha = beta."""
        return self._a_eq_b.value

    @a_eq_b.setter
    def a_eq_b(self, val):
        self._set_factory(self._a_eq_b, val)

    @a_eq_b.deleter
    def a_eq_b(self):
        self._a_eq_b.value = None

    @property
    def alpha(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for alpha angle."""
        return self._alpha.value

    @alpha.setter
    def alpha(self, val):
        self._set_factory(self._alpha, val)

    @alpha.deleter
    def alpha(self):
        self._alpha.value = None

    @property
    def beta(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for beta angle."""
        return self._beta.value

    @beta.setter
    def beta(self, val):
        self._set_factory(self._beta, val)

    @beta.deleter
    def beta(self):
        self._beta.value = None

    @property
    def psi(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for psi angle."""
        return self._psi.value

    @psi.setter
    def psi(self, val):
        self._set_factory(self._psi, val)

    @psi.deleter
    def psi(self):
        self._psi.value = None

    @property
    def bin_eq_bout(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for betain = betaout."""
        return self._bin_eq_bout.value

    @bin_eq_bout.setter
    def bin_eq_bout(self, val):
        self._set_factory(self._bin_eq_bout, val)

    @bin_eq_bout.deleter
    def bin_eq_bout(self):
        self._bin_eq_bout.value = None

    @property
    def betain(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for betain angle."""
        return self._betain.value

    @betain.setter
    def betain(self, val):
        self._set_factory(self._betain, val)

    @betain.deleter
    def betain(self):
        self._betain.value = None

    @property
    def betaout(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for betaout angle."""
        return self._betaout.value

    @betaout.setter
    def betaout(self, val):
        self._set_factory(self._betaout, val)

    @betaout.deleter
    def betaout(self):
        self._betaout.value = None

    @property
    def mu(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for mu angle."""
        return self._mu.value

    @mu.setter
    def mu(self, val):
        self._set_factory(self._mu, val)

    @mu.deleter
    def mu(self):
        self._mu.value = None

    @property
    def eta(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for eta angle."""
        return self._eta.value

    @eta.setter
    def eta(self, val):
        self._set_factory(self._eta, val)

    @eta.deleter
    def eta(self):
        self._eta.value = None

    @property
    def chi(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for chi angle."""
        return self._chi.value

    @chi.setter
    def chi(self, val):
        self._set_factory(self._chi, val)

    @chi.deleter
    def chi(self):
        self._chi.value = None

    @property
    def phi(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for phi angle."""
        return self._phi.value

    @phi.setter
    def phi(self, val):
        return self._set_factory(self._phi, val)

    @phi.deleter
    def phi(self):
        self._phi.value = None

    @property
    def bisect(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for bisect mode."""
        return self._bisect.value

    @bisect.setter
    def bisect(self, val):
        self._set_factory(self._bisect, val)

    @bisect.deleter
    def bisect(self):
        self._bisect.value = None

    @property
    def omega(self) -> Optional[Union[Quantity, Literal["True"]]]:
        """Constraint for omega angle."""
        return self._omega.value

    @omega.setter
    def omega(self, val):
        self._set_factory(self._omega, val)

    @omega.deleter
    def omega(self):
        self._omega.value = None

    def _build_display_table_lines(self) -> List[str]:
        constraint_types = [
            (self._delta, self._nu, self._qaz, self._naz),
            (
                self._a_eq_b,
                self._alpha,
                self._beta,
                self._psi,
                self._bin_eq_bout,
                self._betain,
                self._betaout,
            ),
            (self._mu, self._eta, self._chi, self._phi, self._bisect, self._omega),
        ]
        max_name_width = max(len(con.name) for con in self._all)

        cells = []

        header_cells = []
        header_cells.append("    " + "DET".ljust(max_name_width))
        header_cells.append("    " + "REF".ljust(max_name_width))
        header_cells.append("    " + "SAMP")
        cells.append(header_cells)

        underline_cells = ["    " + "-" * max_name_width] * len(constraint_types)
        cells.append(underline_cells)

        for con_line in zip_longest(*constraint_types):
            row_cells = []
            for con in con_line:
                name = con.name if con is not None else ""
                row_cells.append("   " if con is None or not con.active else "-->")
                row_cells.append(("%-" + str(max_name_width) + "s") % name)
            cells.append(row_cells)

        lines = [" ".join(row_cells).rstrip() for row_cells in cells]
        return lines

    def _report_constraint(self, con: _Constraint) -> str:
        val = getattr(self, con.name)
        if con._type is _con_type.VOID:
            return "    %s" % con.name
        else:
            return f"    {con.name:<5}: {val:.4f}"

    def _report_constraints_lines(self) -> List[str]:
        lines = []
        required = 3 - len(self.constrained)
        if required == 0:
            pass
        elif required == 1:
            lines.append("!   1 more constraint required")
        else:
            lines.append("!   %d more constraints required" % required)
        lines.extend([self._report_constraint(con) for con in self._all if con.active])
        return lines

    @classmethod
    def asdegrees(cls, constraints: "Constraints") -> "Constraints":
        """Create new Constraints object with angles in degrees.

        Parameters
        ----------
        constraints: Constraints
            Input Constraints object

        Returns
        -------
        Constraints
            New Constraints object with angles in degrees.
        """
        res = cls(constraints.asdict, indegrees=constraints.indegrees)
        res.indegrees = True
        return res

    @classmethod
    def asradians(cls, constraints: "Constraints") -> "Constraints":
        """Create new Constraints object with angles in radians.

        Parameters
        ----------
        constraints: Constraints
            Input Position object

        Returns
        -------
        Constraints
            New Constraints object with angles in radians.
        """
        res = cls(constraints.asdict, indegrees=constraints.indegrees)
        res.indegrees = False
        return res

    def is_fully_constrained(self, con: Optional[_Constraint] = None) -> bool:
        """Check if configuration is fully constrained.

        Parameters
        ----------
        con: _Constraint, default = None
            Check if there are available constraints is the same category as the
            input constraint. If parameter is None, check for all constraint
            categories.

        Returns
        -------
        bool:
            True if there aren't any constraints available either in the input
            constraint category or no constraints are available.
        """
        if con is None:
            return len(self.constrained) >= 3

        _max_constrained = {
            _con_category.DETECTOR: 1,
            _con_category.REFERENCE: 1,
            _con_category.SAMPLE: 3,
        }
        count_constrained = len(
            {c for c in self.constrained if c._category is con._category}
        )
        return count_constrained >= _max_constrained[con._category]

    def is_current_mode_implemented(self) -> bool:
        """Check if current constraint set is implemented.

        Configuration needs to be fully constraint for this method to work.

        Returns
        -------
        bool:
            True if current constraint set is supported.
        """
        if not self.is_fully_constrained():
            raise ValueError("Three constraints required")

        count_detector = len(
            {c for c in self.constrained if c._category is _con_category.DETECTOR}
        )
        count_reference = len(
            {c for c in self.constrained if c._category is _con_category.REFERENCE}
        )
        count_sample = len(
            {c for c in self.constrained if c._category is _con_category.SAMPLE}
        )
        if count_sample == 3:
            if (
                set(self.constrained) == {self._chi, self._phi, self._eta}
                or set(self.constrained) == {self._chi, self._phi, self._mu}
                or set(self.constrained) == {self._chi, self._eta, self._mu}
                or set(self.constrained) == {self._phi, self._eta, self._mu}
            ):
                return True
            return False

        if count_sample == 1:
            return self._omega not in set(self.constrained) and self._bisect not in set(
                self.constrained
            )

        if count_reference == 1:
            return (
                {self._chi, self._phi}.issubset(self.constrained)
                or {self._chi, self._eta}.issubset(self.constrained)
                or {self._chi, self._mu}.issubset(self.constrained)
                or {self._mu, self._eta}.issubset(self.constrained)
                or {self._mu, self._phi}.issubset(self.constrained)
                or {self._eta, self._phi}.issubset(self.constrained)
            )

        if count_detector == 1:
            return (
                {self._chi, self._phi}.issubset(self.constrained)
                or {self._mu, self._eta}.issubset(self.constrained)
                or {self._mu, self._phi}.issubset(self.constrained)
                or {self._mu, self._chi}.issubset(self.constrained)
                or {self._eta, self._phi}.issubset(self.constrained)
                or {self._eta, self._chi}.issubset(self.constrained)
                or {self._mu, self._bisect}.issubset(self.constrained)
                or {self._eta, self._bisect}.issubset(self.constrained)
                or {self._omega, self._bisect}.issubset(self.constrained)
            )

        return False

    def clear(self) -> None:
        """Remove all constraints."""
        for con in self._all:
            delattr(self, con.name)
