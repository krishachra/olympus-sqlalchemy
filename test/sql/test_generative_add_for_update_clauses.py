"""Tests for GenerativeSelect.add_for_update() — multiple locking clauses.

Verifies that a SELECT statement can carry multiple FOR UPDATE / FOR SHARE
clauses with independent OF targets, as described in sqlalchemy/sqlalchemy#12101.

PostgreSQL key_share parameter semantics (matches with_for_update() behaviour):
  key_share=True alone            -> FOR NO KEY UPDATE
  key_share=True, read=True       -> FOR KEY SHARE

All tests are pure compile tests (no database connection required).
"""
from __future__ import annotations

from sqlalchemy import column
from sqlalchemy import select
from sqlalchemy import table
from sqlalchemy.testing import AssertsCompiledSQL
from sqlalchemy.testing import fixtures


class AddForUpdateExistsTest(fixtures.TestBase):
    """Verify the add_for_update() method is present and generative."""

    def test_add_for_update_is_callable(self):
        t1 = table("t1", column("id"))
        stmt = select(t1)
        assert hasattr(stmt, "add_for_update"), (
            "Select has no add_for_update() method — feature not yet implemented"
        )

    def test_add_for_update_returns_select(self):
        t1 = table("t1", column("id"))
        stmt = select(t1)
        new_stmt = stmt.add_for_update()
        assert new_stmt is not stmt, "add_for_update() must be generative"
        assert type(new_stmt) is type(stmt)


class AddForUpdateSinglePGTest(fixtures.TestBase, AssertsCompiledSQL):
    """Single add_for_update() call — PostgreSQL dialect output.

    Each test verifies that add_for_update() accepts the same keyword
    arguments as with_for_update() and renders the same per-clause SQL.
    """

    __dialect__ = "postgresql"

    def test_add_for_update_no_args(self):
        """add_for_update() with no arguments produces FOR UPDATE."""
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(),
            "SELECT t1.id, t1.val FROM t1 FOR UPDATE",
        )

    def test_add_for_update_of_table(self):
        """add_for_update(of=t1) produces FOR UPDATE OF t1."""
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(of=t1),
            "SELECT t1.id, t1.val FROM t1 FOR UPDATE OF t1",
        )

    def test_add_for_update_read(self):
        """add_for_update(read=True) produces FOR SHARE."""
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(read=True),
            "SELECT t1.id, t1.val FROM t1 FOR SHARE",
        )

    def test_add_for_update_read_of(self):
        """add_for_update(read=True, of=t1) produces FOR SHARE OF t1."""
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(read=True, of=t1),
            "SELECT t1.id, t1.val FROM t1 FOR SHARE OF t1",
        )

    def test_add_for_update_nowait(self):
        """add_for_update(nowait=True) produces FOR UPDATE NOWAIT."""
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(nowait=True),
            "SELECT t1.id, t1.val FROM t1 FOR UPDATE NOWAIT",
        )

    def test_add_for_update_skip_locked(self):
        """add_for_update(skip_locked=True) produces FOR UPDATE SKIP LOCKED."""
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(skip_locked=True),
            "SELECT t1.id, t1.val FROM t1 FOR UPDATE SKIP LOCKED",
        )

    def test_add_for_update_no_key_update(self):
        """add_for_update(key_share=True) produces FOR NO KEY UPDATE.

        PostgreSQL: key_share=True without read=True maps to FOR NO KEY UPDATE,
        which is a weaker exclusive lock that does not block FOR KEY SHARE readers.
        This matches the existing with_for_update(key_share=True) behaviour.
        """
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(key_share=True),
            "SELECT t1.id, t1.val FROM t1 FOR NO KEY UPDATE",
        )

    def test_add_for_update_key_share_with_read(self):
        """add_for_update(key_share=True, read=True) produces FOR KEY SHARE.

        PostgreSQL: key_share=True combined with read=True maps to FOR KEY SHARE,
        a shared lock that is compatible with FOR NO KEY UPDATE holders.
        This matches the existing with_for_update(key_share=True, read=True)
        behaviour.
        """
        t1 = table("t1", column("id"), column("val"))
        self.assert_compile(
            select(t1).add_for_update(key_share=True, read=True),
            "SELECT t1.id, t1.val FROM t1 FOR KEY SHARE",
        )


class MultipleLockingClausesPGTest(fixtures.TestBase, AssertsCompiledSQL):
    """Two or more locking clauses on a single SELECT — PostgreSQL dialect.

    The core feature: add_for_update() appends a new locking clause instead
    of replacing the existing one, so a single query can lock different tables
    with different strengths in one round-trip.
    """

    __dialect__ = "postgresql"

    def test_for_update_of_t1_then_for_share_of_t2(self):
        """with_for_update(of=t1) + add_for_update(read, of=t2) = two clauses."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(of=t1)
            .add_for_update(read=True, of=t2),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR UPDATE OF t1 FOR SHARE OF t2",
        )

    def test_for_share_of_t1_then_for_update_of_t2(self):
        """Clause order is preserved: FOR SHARE first, then FOR UPDATE."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(read=True, of=t1)
            .add_for_update(of=t2),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR SHARE OF t1 FOR UPDATE OF t2",
        )

    def test_two_for_share_clauses_different_of(self):
        """Two separate FOR SHARE clauses with different OF targets."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(read=True, of=t1)
            .add_for_update(read=True, of=t2),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR SHARE OF t1 FOR SHARE OF t2",
        )

    def test_three_chained_locking_clauses(self):
        """Three chained add_for_update calls produce three locking clauses.

        Uses FOR UPDATE, FOR SHARE, and FOR NO KEY UPDATE on three tables.
        FOR NO KEY UPDATE is produced by key_share=True without read=True.
        """
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        t3 = table("t3", column("id"))
        self.assert_compile(
            select(t1, t2, t3)
            .with_for_update(of=t1)
            .add_for_update(read=True, of=t2)
            .add_for_update(key_share=True, of=t3),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk, t3.id AS id_2 "
            "FROM t1, t2, t3 "
            "FOR UPDATE OF t1 FOR SHARE OF t2 FOR NO KEY UPDATE OF t3",
        )

    def test_with_for_update_resets_all_locking_clauses(self):
        """Calling with_for_update() resets all previously-added locking clauses."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(of=t1)
            .add_for_update(read=True, of=t2)
            .with_for_update(of=t2),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR UPDATE OF t2",
        )

    def test_add_for_update_without_prior_with_for_update(self):
        """add_for_update() can be called as the sole locking method."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2).add_for_update(of=t1),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR UPDATE OF t1",
        )

    def test_nowait_on_first_skip_locked_on_second(self):
        """NOWAIT and SKIP LOCKED on separate clauses are independently rendered."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(of=t1, nowait=True)
            .add_for_update(read=True, of=t2, skip_locked=True),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR UPDATE OF t1 NOWAIT FOR SHARE OF t2 SKIP LOCKED",
        )

    def test_for_key_share_alongside_for_update(self):
        """FOR KEY SHARE (key_share=True, read=True) alongside FOR UPDATE.

        key_share=True, read=True -> FOR KEY SHARE (shared lock compatible with
        FOR NO KEY UPDATE holders).  This is distinct from key_share=True alone,
        which produces FOR NO KEY UPDATE.
        """
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(of=t1)
            .add_for_update(read=True, key_share=True, of=t2),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR UPDATE OF t1 FOR KEY SHARE OF t2",
        )

    def test_column_of_target_resolves_to_table(self):
        """of= accepts column expressions; they resolve to the parent table."""
        t1 = table("t1", column("id"), column("val"))
        t2 = table("t2", column("id"), column("fk"))
        self.assert_compile(
            select(t1, t2)
            .with_for_update(of=t1.c.id)
            .add_for_update(read=True, of=t2.c.id),
            "SELECT t1.id, t1.val, t2.id AS id_1, t2.fk "
            "FROM t1, t2 FOR UPDATE OF t1 FOR SHARE OF t2",
        )

    def test_plain_select_has_no_locking_clause(self):
        """A plain select without any locking call produces no FOR * clause."""
        t1 = table("t1", column("id"))
        self.assert_compile(
            select(t1),
            "SELECT t1.id FROM t1",
        )


class CacheKeyTest(fixtures.TestBase):
    """Cache key differentiation for multiple locking clauses."""

    def test_different_locking_configs_have_different_cache_keys(self):
        """Two statements with different locking configurations must not share
        a cache key, even if they select from the same tables."""
        t1 = table("t1", column("id"))
        t2 = table("t2", column("id"))
        stmt_a = (
            select(t1, t2)
            .with_for_update(of=t1)
            .add_for_update(read=True, of=t2)
        )
        stmt_b = (
            select(t1, t2)
            .with_for_update(of=t2)
            .add_for_update(read=True, of=t1)
        )
        assert stmt_a._generate_cache_key() != stmt_b._generate_cache_key(), (
            "Statements with swapped OF targets must have different cache keys"
        )

    def test_identical_locking_configs_have_same_cache_key(self):
        """Two identically-constructed statements must share a cache key."""
        t1 = table("t1", column("id"))
        t2 = table("t2", column("id"))

        def make():
            return (
                select(t1, t2)
                .with_for_update(of=t1)
                .add_for_update(read=True, of=t2)
            )

        assert make()._generate_cache_key() == make()._generate_cache_key(), (
            "Identically-constructed statements must share the same cache key"
        )

    def test_single_vs_multiple_clauses_have_different_cache_keys(self):
        """A one-clause statement must differ in cache key from a two-clause one."""
        t1 = table("t1", column("id"))
        t2 = table("t2", column("id"))
        stmt_one = select(t1, t2).with_for_update(of=t1)
        stmt_two = (
            select(t1, t2)
            .with_for_update(of=t1)
            .add_for_update(read=True, of=t2)
        )
        assert stmt_one._generate_cache_key() != stmt_two._generate_cache_key(), (
            "One-clause and two-clause statements must have different cache keys"
        )
class AddForUpdateOtherDialectTest(fixtures.TestBase, AssertsCompiledSQL):
    """Check add_for_update() with non-PostgreSQL dialects."""

    def test_mysql_uses_first_locking_clause(self):
        t1 = table("t1", column("id"))
        t2 = table("t2", column("id"))

        self.assert_compile(
            select(t1, t2)
            .with_for_update(of=t1)
            .add_for_update(of=t2),
            "SELECT t1.id, t2.id AS id_1 FROM t1, t2 FOR UPDATE",
            dialect="mysql",
        )

    def test_oracle_renders_multiple_locking_clauses(self):
        self.assert_compile(
            select(table("t1", column("id")))
            .with_for_update()
            .add_for_update(),
            "SELECT t1.id FROM t1 FOR UPDATE FOR UPDATE",
            dialect="oracle",
        )
