# DexRemo task suite

Nine real-robot removal tasks in three families. Each task needs a target to be separated from something that holds it: an adhesive bond, a stain on a surface, or the grains of a particulate medium.

| Family | Tasks | What the hand has to do |
|---|---|---|
| A. Adhesive detachment and self-cleaning | A1–A5 | Find an edge, then peel, pry or pull the target off its substrate |
| B. Surface mark removal | B1–B2 | Wipe a marked region until it is clean |
| C. Occluded object retrieval | C1–C2 | Dig through sand or litter to uncover a buried target |

The paper uses two tiers:
- **Core benchmark:** A1–A4, B1 and C1. Every input configuration is compared on these.
- **Extension scenarios:** A5, B2 and C2. These add coverage and are evaluated only with the full model.

The full protocol is in the [paper](https://arxiv.org/abs/2611.15981): see the "Experimental Evaluation" section and the appendix "Task Details and Success Criteria".

## Tasks

| | ID | Task | Held by | Varied in training | Held-out tests |
|---|---|---|---|---|---|
| <img src="img/a1.jpg" width="120"> | A1 | Barnacle removal from a turtle shell | Hot-melt adhesive | Barnacle pose | Unseen barnacle size, pose and colour |
| <img src="img/a2.jpg" width="120"> | A2 | Printed part removal from a 3D-printer build plate | Nano-adhesive pad | Part pose | Unseen shapes and colours; unseen pose |
| <img src="img/a3.jpg" width="120"> | A3 | Blu-Tack removal from an acrylic plate | Blu-Tack adhesion | Blu-Tack shape and pose | Unseen shape, colour and placement |
| <img src="img/a4.jpg" width="120"> | A4 | Wood-ear fungus removal from a log | Hot-melt adhesive | Wood-ear pose | Unseen wood-ear pose and size |
| <img src="img/a5.jpg" width="120"> | A5 | Fingertip self-cleaning | Blu-Tack on the fingertip | Residue shape and pose | Unseen residue shape, pose and colour |
| <img src="img/b1.jpg" width="120"> | B1 | Wiping marker stains off a ceramic plate (sponge tip) | Pigment on the surface | Stain location and shape | Unseen location, shape and colour |
| <img src="img/b2.jpg" width="120"> | B2 | Wiping ink off silicone skin (cotton tip) | Pigment on the surface | Stain location and shape | Unseen location, shape and colour |
| <img src="img/c1.jpg" width="120"> | C1 | Fossil excavation in sand | Sand grains | Fossil pose | Unseen pose; unseen fossils |
| <img src="img/c2.jpg" width="120"> | C2 | Cat-litter clump removal | Litter grains | Clump pose and size | Unseen clump colour and pose |

## Objects and preparation

Reset each trial to this state before it starts. All sizes are nominal.

| ID | Object | Material | Preparation |
|---|---|---|---|
| A1 | Barnacle model, 50 × 40 × 40 mm | PLA or resin target on a turtle-shell substrate | Apply 0.35 g of hot-melt adhesive (glue layer ≥ 3 mm) and wait 60 s |
| A2 | Printed part, 65 × 30 × 30 mm; adhesive pad 15 × 15 mm | PLA part on a build plate, nano-adhesive film | Attach the part to the cleaned plate and press for 10 s |
| A3 | Blu-Tack patch, 150 × 100 × 1 mm (about 20 g) | Blu-Tack on an acrylic plate | Knead to shape, then press with about 5 N for 5 s |
| A4 | Wood-ear model, 50 × 40 mm, on a log 200 mm long and 100 mm in diameter | Soft target on a birch log, hot-melt adhesive | Apply adhesive at the root and wait 60 s |
| A5 | Blu-Tack residue, 20 × 20 × 5 mm | Blu-Tack on the fingertip shell | Stick the residue to a fingertip; vary its shape and pose |
| B1 | Marker stain in a 120 × 120 mm region on a 255 mm plate | Purple marker on a ceramic plate; sponge fingertip | Draw the stain in the region; wet the sponge with 2 ml of water |
| B2 | Ink mark in a 120 × 120 mm region on a 90 × 400 × 30 mm skin | Ink on silicone skin; cotton fingertip | Draw the mark and wait 30 s |
| C1 | Fossil model, 80 × 40 × 30 mm, in a 350 × 500 × 60 mm tray | Beach sand | Bury the fossil 15 mm deep and flatten the surface |
| C2 | Litter clump, 70 × 15 × 20 mm | Cat litter | Embed the clump and level the litter around it |

## Held-out conditions

| ID | Held-out conditions |
|---|---|
| A1 | Barnacles of 40 × 30 × 30 mm and 60 × 50 × 50 mm; an unseen shell |
| A2 | Triangular and quadrilateral prisms; part yaw ±30° |
| A3 | Blue Blu-Tack; ring and strip shapes; placement ±50 mm |
| A4 | Log rotated ±45°; wood-ear moved ±30 mm |
| A5 | Clay instead of Blu-Tack; thin-sheet and thick-blob shapes |
| B1 | Unseen location and shape; green marker |
| B2 | Unseen location and shape; blue ink |
| C1 | Unseen fossils (80 × 40 × 30 mm and 70 × 30 × 30 mm); depths of 10 and 20 mm; sand camouflage |
| C2 | Colour-matched clump; pose ±60 mm |

## Success criteria

A trial ends when the success condition is met or after 120 s (1800 steps at 15 Hz). No scripted recovery or manual intervention is allowed during a trial.

| ID | Success |
|---|---|
| A1, A4 | Target detached and held at least 10 mm above the surface for 1 s, with no visible damage |
| A2 | Part detached and held clear of the plate for 1 s, without being flung off |
| A3 | Blu-Tack removed, with at most 5 % residue by area |
| A5 | Residue fully removed, judged visually |
| B1, B2 | At least 90 % of the marked region cleaned |
| C1 | At least 80 % of the fossil exposed, with the trench no deeper than 20 mm |
| C2 | At least 80 % of the clump surface exposed |

How to score:
- **No visible damage** means no gouge or tear larger than 2 mm.
- **Cleaned or exposed area** is measured inside the predefined region. Take a photo before and after the trial, compare the two in HSV space with a fixed threshold, and count the changed pixels.
- **Manual scoring:** when a trial has to be judged by eye, three raters label it, and the label is checked once against the recorded video.

## Setup

![Experimental setup](img/setup.jpg)

**Hand and workspace**
- The hand points down over a tabletop workspace of 820 × 1156 mm.
- A linear stage moves the hand vertically over z ∈ [−205, −115] mm. The tabletop is z = 0 and +z points up.

**Cameras**
- Three RGB cameras: two external cameras and one on the wrist.
- Each runs at 480 × 640 and 15 Hz, synchronised to within 50 ms.

Camera poses are given in the wrist frame. Positions are in mm, orientations in degrees.

| Camera | Position | Orientation |
|---|---|---|
| Left external | (150, 440, 180) | (0, 5, 15) |
| Right external | (150, −450, 180) | (0, −5, −15) |
| Wrist | (−200, 0, −30) | (45, 0, 0) |

**Demonstrations**
- Collect 20 successful teleoperated demonstrations per task under nominal conditions.
- Training variations are listed in the [Tasks](#tasks) table.

## Sourcing the objects

*To be added:* where to buy or how to make each target, substrate and consumable.

## Citation

If you use this task suite, please cite the paper. The BibTeX is in the [repository README](../README.md#citation).
