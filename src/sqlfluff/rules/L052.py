"""Implementation of Rule L052."""
from typing import List, NamedTuple
from sqlfluff.core.config import FluffConfig

from sqlfluff.core.parser import SymbolSegment
from sqlfluff.core.parser.segments.raw import RawSegment

from sqlfluff.core.rules import BaseRule, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import SegmentSeekerCrawler
from sqlfluff.core.rules.doc_decorators import (
    document_configuration,
    document_fix_compatible,
    document_groups,
)
from sqlfluff.utils.functional import Segments, sp
from sqlfluff.utils.reflow import ReflowSequence


class SegmentMoveContext(NamedTuple):
    """Context information for moving a segment."""

    anchor_segment: RawSegment
    is_one_line: bool
    before_segment: Segments
    whitespace_deletions: Segments


@document_groups
@document_fix_compatible
@document_configuration
class Rule_L052(BaseRule):
    """Statements must end with a semi-colon.

    **Anti-pattern**

    A statement is not immediately terminated with a semi-colon. The ``•`` represents
    space.

    .. code-block:: sql
       :force:

        SELECT
            a
        FROM foo

        ;

        SELECT
            b
        FROM bar••;

    **Best practice**

    Immediately terminate the statement with a semi-colon.

    .. code-block:: sql
       :force:

        SELECT
            a
        FROM foo;
    """

    groups = ("all",)
    config_keywords = ["multiline_newline", "require_final_semicolon"]
    crawl_behaviour = SegmentSeekerCrawler({"statement"})

    def _eval(self, context: RuleContext) -> List[LintResult]:
        """Statements must end with a semi-colon."""
        # Config type hints
        self.multiline_newline: bool
        self.require_final_semicolon: bool
        config = context.config

        # Assert that we're working with a statement
        assert context.segment.is_type("statement")

        # Is it a multiline statement?
        is_multiline = (
            context.segment.pos_marker.working_line_no
            != context.segment.pos_marker.working_loc_after(context.segment.raw)[0]
        )
        # Mutate the config if required
        if self.multiline_newline and is_multiline:
            config = FluffConfig.from_kwargs(config=context.config)
            # Setting the line position to "alone" ensures it will be on it's own line.
            config.set_value(
                config_path=["layout", "type", "statement_terminator", "line_position"],
                val="alone",
            )

        next_code = (
            Segments(*context.parent_stack[0].segments)
            .select(select_if=sp.is_code(), start_seg=context.segment)
            .first()
            .get()
        )

        # Have we found a semicolon?
        if next_code and next_code.is_type("statement_terminator"):
            self.logger.debug("Assessing terminator position: %s", next_code)
            # So, reflow isn't quite smart enough to be as specific as we want to
            # be with this rule. Only in the multiline newline case. In that scenario
            # we don't just want it to be on a newline after the query, but _immediately_
            # after. To lint that effectively, we first assess whether to _move_
            # the terminator here, and then reflow _after the move_.

            seq = ReflowSequence.from_around_target(
                next_code,
                root_segment=context.parent_stack[0],
                config=config,
            )

            if self.multiline_newline and is_multiline:
                # Get the last code element of the statement
                last_statement_code = Segments(*context.segment.raw_segments).last(sp.is_code()).get()
                self.logger.debug("Last code element of statement on line %s: %s", last_statement_code.pos_marker.working_line_no, last_statement_code)
                # Is it on the _next_ line?
                if next_code.pos_marker.working_line_no == last_statement_code.pos_marker.working_line_no + 1:
                    self.logger.debug("Semi-colon is on the correct line.")
                else:
                    self.logger.debug("Semi-colon is on the wrong line: %s not immediately after %s", next_code.pos_marker.working_line_no, last_statement_code.pos_marker.working_line_no)
                    #  Ok we need to move it. Insert it after the next newline after last_statement_code
                    next_nl = (
                        Segments(*context.parent_stack[0].segments)
                        .select(select_if=sp.is_type("newline"), start_seg=context.segment)
                        .first()
                        .get()
                    )
                    seq = seq.without(next_code).insert(next_code, next_nl, pos="after")
                    self.logger.warning("Embodied fixed %s", seq.get_fixes())
                    
            else:
                # TODO: Do we need to do anything fancy in this case?
                pass

            # Reflow the semicolon, to enforce spacing and line position.
            fixes = seq.rebreak().get_fixes()
            if fixes:
                if self.multiline_newline:
                    description = "Semi-colon should be on it's own line immediately after multiline statement."
                else:
                    description = (
                        "Semi-colon follow statement immediately on the same line."
                    )
                return LintResult(next_code, fixes, description=description)

        # If we haven't, and we should
        elif self.require_final_semicolon:
            # We need a semicolon, but there isn't one.
            self.logger.debug("Required terminator not found.")
            # Insert it.
            fixes = (
                ReflowSequence.from_around_target(
                    # Focus around the last raw element of the target
                    context.segment.raw_segments[-1],
                    root_segment=context.parent_stack[0],
                    config=context.config,
                    # We're inserting after so we only need the part of the sequence which is after.
                    sides="after",
                )
                .insert(
                    SymbolSegment(raw=";", type="statement_terminator"),
                    context.segment,
                    pos="after",
                )
                .rebreak()
                .get_fixes()
            )
            ##### TODO: Probably work out the anchor here based on where the fixes are anchored. Otherwise it will be wierd.
            return LintResult(context.segment, fixes)

        return LintResult()

        # Is it the end of the file and do we require semicolons?
        if context.segment.is_type("end_of_file") and self.require_final_semicolon:
            # Find previous code segment.
            # It should be a direct child of the root segment.
            last_code = (
                Segments(*context.parent_stack[0].segments).last(sp.is_code()).get()
            )
            self.logger.debug("Found end of file. Last Code: %s", last_code)
            # Make sure it's a semicolon. Fine if it is.
            if last_code.is_type("statement_terminator"):
                return LintResult()

            # We need a semicolon, but there isn't one.
            self.logger.debug("Required terminator not found.")
            # Insert it.
            fixes = (
                ReflowSequence.from_around_target(
                    # Focus around the last raw element of the target
                    last_code.raw_segments[-1],
                    root_segment=context.parent_stack[0],
                    config=context.config,
                    # We're inserting after so we only need the part of the sequence which is after.
                    sides="after",
                )
                .insert(
                    SymbolSegment(raw=";", type="statement_terminator"),
                    last_code,
                    pos="after",
                )
                .rebreak()
                .get_fixes()
            )
            return LintResult(last_code, fixes)

        # Have we found a pre-existing semicolon?
        elif context.segment.is_type("statement_terminator"):
            # Reflow the semicolon, to enforce spacing and line position.
            fixes = (
                ReflowSequence.from_around_target(
                    context.segment,
                    root_segment=context.parent_stack[0],
                    config=context.config,
                )
                .rebreak()
                .get_fixes()
            )
            if fixes:
                return LintResult(context.segment, fixes)

        return LintResult()
