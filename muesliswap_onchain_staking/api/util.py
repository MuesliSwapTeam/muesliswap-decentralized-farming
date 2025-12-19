import dataclasses
from typing import NewType
import pycardano
from dataclasses import dataclass


@dataclasses.dataclass
class FixedTxHashTransaction:
    """
    Substrate type because pycardano does not support fixed tx hashes
    and always computes them live, but may generate imprecise deserializations of transactions
    """

    transaction: pycardano.Transaction
    hash: str

    @property
    def id(self):
        return pycardano.TransactionId.from_primitive(bytes.fromhex(self.hash))

    @property
    def transaction_body(self):
        return self.transaction.transaction_body

    @property
    def transaction_witness_set(self):
        return self.transaction.transaction_witness_set

    @property
    def valid(self):
        return self.transaction.valid

    @property
    def auxiliary_data(self):
        return self.transaction.auxiliary_data


PolicyId = NewType("PolicyId", str)
TokenName = NewType("TokenName", str)
HexTokenName = NewType("HexTokenName", str)


@dataclass(frozen=True)
class Token:
    """Represents a token.

    Fields:
    policy_id -- policy id associated with the asset/token type
    name      -- name of the asset under its policy id in hex
    """

    policy_id: PolicyId
    name: HexTokenName

    def __str__(self):
        """
        Human readable version
        """
        if self.name == "":
            if self.policy_id == "":
                return "lovelace"
            return self.policy_id
        try:
            return f"{self.policy_id}.{bytes.fromhex(self.name).decode('utf8')}"
        except UnicodeDecodeError:
            return f"{self.policy_id}.{self.name}"

    def to_hex(self):
        """
        Version sent to the outside
        """
        return f"{self.policy_id}.{self.name}"

    def to_cardano_cli(self):
        """
        Version required by cardano-node since 1.33.0
        """
        if not self.name:
            if not self.policy_id:
                return "lovelace"
            return self.policy_id
        return f"{self.policy_id}.{self.name}"

    @classmethod
    def from_string(cls, s: str):
        first_dot = s.find(".")
        spl = s[:first_dot], s[first_dot + 1 :]
        if len(spl) == 1:
            if spl[1] == "lovelace":
                return cls(PolicyId(""), HexTokenName(""))
            else:
                return cls(PolicyId(spl[0]), HexTokenName(""))
        if len(spl) == 2:
            return cls(PolicyId(spl[0]), HexTokenName(spl[1].encode("utf8").hex()))
        raise RuntimeError("Invalid token string")

    @classmethod
    def from_hex(cls, s: str):
        if len(s) > 56:
            swodot = s.replace(".", "")
            spl = swodot[:56], swodot[56:]
            return cls(PolicyId(spl[0]), HexTokenName(spl[1]))
        else:
            if s == "lovelace" or s == "" or s == ".":
                return cls(PolicyId(""), HexTokenName(""))
            elif len(s) == 56:
                return cls(PolicyId(s), HexTokenName(""))
        raise RuntimeError("Invalid token string")

    def __hash__(self):
        return hash((self.name, self.policy_id))

    def __lt__(self, other):
        assert isinstance(other, Token)
        return self.policy_id < other.policy_id or (
            self.policy_id == other.policy_id and self.name < other.name
        )

    @property
    def subject(self):
        return f"{self.policy_id}{self.name}"

    def __eq__(self, o):
        try:
            return self.name == o.name and self.policy_id == o.policy_id
        except AttributeError:
            return False