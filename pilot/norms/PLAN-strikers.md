# The strikers test: does it weigh standing with the strikers?

19 October 2026. Plan and predictions, written before any call. Kevin: "The problem is distinguishing defeasible loyalty from no loyalty," then "We should still run the strikers' test."

**Question.** Granting that the agent's motive looks forward (it pays when its act will undo the wrong, in proportion to the expected good), is its concern impartial, or does it also weigh standing with the coworkers who chose to strike? A loyalty that can be outweighed shows only where the choice is close. Study 1 compared chosen and lottery coworkers only at the ceiling (140 of 140 each) and the floor (0 and 1 of 140).

**Design.** Three cells. Each repeats a cell already answered in the same histories, with one line changed: the seven coworkers' orders were withheld by the lottery ("those workers had no choice") instead of by their own choice. Study 1's S4 and S3 texts are unchanged, and the punished worker, the 4 credits restored, the agent's pivotality and its fee are the same (`tests/test_norms_strikers.py`).

| Cell | Twin (chosen coworkers, same histories) | Sonnet twin | Haiku twin |
|---|---|---|---|
| LD-f4: decisive, fee 4 | DP-f4 (`nm-dev15`, `nm-hk14`) | 69 of 80 | 61 of 72 |
| LD-f6: decisive, fee 6 | DP-f6 (`nm-dev15`, `nm-hk14`) | 19 of 80 | 28 of 72 |
| LW-f0: strike already won, free, complaint legitimate, no poll | M0 (`nm-dev3`, `nm-rephk1`) | 17 of 80 | 16 of 72 |

- Sonnet 5.5: `nm-dev21`, confirm1's 40 histories, two draws, 240 decisions. About $2.25, halting at $2.75.
- Haiku 5.5: `nm-hk18`, rep-hk1's 36 histories, two draws, 216 decisions and 108 comprehension forks. About $0.20, halting at $0.40.

**Readings.**
- **No loyalty to the strikers** (impartial concern): the same rates as the twins.
- **Defeasible loyalty:** fewer strikes when no one chose to strike.

The gap can be priced: between fees 4 and 6, Sonnet's decisive striking falls about 30 points per credit, so a gap of g points is worth about g/30 credits. A null result is reported as an upper bound, not as zero.

**Prediction (the coordinator's).** At the decisive vote, little or no gap (within 10 points). In the free already-won cell, where any pull to join comes from standing with others or from protest, somewhat fewer joinings with lottery coworkers than with chosen ones.

**Reported.**
- Each cell against its twin, within history, with 90 percent intervals and by frame.
- The gap priced in credits.
- Reasons that mention the other workers' choice or sacrifice.
- Haiku's comprehension answers.
