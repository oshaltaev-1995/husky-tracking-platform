# P10B generated-media handoff

**Completion:** P10B integrated and visually accepted all 60 synthetic portraits. This
document remains the reproducible inventory, validation, and replacement runbook for
the `dog-media-v1` set.

## Paths, versions, and commands

- generation guide: `docs/DOG_IMAGE_GENERATION_GUIDE.md`;
- canonical manifest: `docs/dog-media-manifest.json`;
- manifest version/cache token: `dog-media-v1`;
- final asset directory: `frontend/public/media/dogs/`;
- required output: WebP, `1086 × 1448 px`, `3:4`;
- expected URL: `/media/dogs/<uuid>.webp?v=dog-media-v1`.

From `backend/`, validate the P10A identity manifest at any time:

```bash
uv run python -m app.media.validate
```

After all generated assets are present, run the strict P10B gate:

```bash
uv run python -m app.media.validate --require-assets --strict-assets
```

The validator reports expected/found counts and min/median/max file size. Prefer direct
target-size WebP export. When a consistent re-encode is useful, put an untouched staging
set under ignored `media/dogs-source/` and run the non-overwriting optimizer from
`backend/`:

```bash
uv run python -m app.media.optimize \
  --source-directory ../media/dogs-source \
  --output-directory ../media/dogs-optimized
```

The command first strictly validates all inputs, requires a separate empty output,
uses `cwebp` photo quality 86 with metadata stripped, validates all outputs, and reports
its `cwebp` version plus file-size distribution. Visually compare every optimized file
before moving the approved set into `frontend/public/media/dogs/`; re-encoding is not a
substitute for generation or visual QA.

## Exact filename inventory

| Dog | Required filename |
| --- | --- |
| Aurora | `9422673b-331b-5e72-a700-5fff0574a209.webp` |
| Atlas | `ff40af5f-64c8-5c5a-9878-300c3ace89f1.webp` |
| Freya | `fa2ac485-6690-50a0-a437-815b3f0b7dbb.webp` |
| Fjord | `35eaa15f-1862-5f9c-865e-5897177b384a.webp` |
| Cedar | `7addc940-1af5-5654-8307-e50355fdf717.webp` |
| Cinder | `a69a0e27-ca79-5532-9d18-ec2ee2d010ed.webp` |
| Cosmo | `cceb0d6e-57d4-59d1-b48f-3b00f659bf32.webp` |
| Clover | `c89f3719-ed0a-56fc-bffb-a5205aab98c9.webp` |
| Coast | `13cd6536-29c9-57d7-8213-432ae65646ab.webp` |
| Dune | `abe8a601-e107-54c8-87dc-c5a4291a8a2a.webp` |
| Delta | `c05522e9-9eb4-53c1-b5d7-81b502d8219d.webp` |
| Django | `b265ec9a-985f-5533-9142-7ba9d59f899f.webp` |
| Daisy | `cd928571-5774-5f21-95c6-d4a5817b28ed.webp` |
| Drift | `ef3ad3d3-4f6e-5b9d-bd77-296901b586c7.webp` |
| Harbor | `cc6697cf-2d7d-53ad-8102-e34ace73657f.webp` |
| Hazel | `f588e62a-368d-5f14-a5b4-b641f1b18cae.webp` |
| Hugo | `92c788d0-4a84-53ec-8ec4-6962a1cddaa4.webp` |
| Hilda | `f78ce4cd-6cef-5ae8-a1bd-19a9005114f9.webp` |
| Halo | `210e10ac-e9e9-557c-b4ff-960b89383091.webp` |
| Koda | `e5f9df9a-4e6d-5aef-b3c7-f1134e73aec0.webp` |
| Kira | `2b0c952d-dc98-521d-a9e7-95f99fedcd0b.webp` |
| Kenzo | `24d0c5f3-1900-5e63-bde2-a54f8be09833.webp` |
| Kaia | `d6505bb8-c94f-5936-81e0-df524d160f07.webp` |
| Kepler | `978fa7d2-9252-51d3-8296-29631b3c116e.webp` |
| Kismet | `0864342e-3c74-557f-921e-34b470977871.webp` |
| Maple | `d8e8f71e-f334-5a35-b160-c0a453b3b092.webp` |
| Magnus | `700ce6b9-68d3-57f4-9bce-93371f229e22.webp` |
| Mabel | `54ccbc70-8919-5b5f-8fcc-ef6a92b4237b.webp` |
| Milo | `4946b7f5-0841-5ae4-8e2d-52025de0d191.webp` |
| Mistral | `dba1a0cb-e8d8-5782-90cc-eb91cd7f5cc5.webp` |
| Nova | `6415eb4a-17f2-5878-b2cc-d04803f30245.webp` |
| Niko | `aa6ffc26-e516-5f00-92aa-38402aa4ce80.webp` |
| Nala | `fdd0eebf-1aa0-59b6-88d0-6435cb941394.webp` |
| Nimbus | `ee68c2ea-71a5-5da0-b552-0d0d3dc31804.webp` |
| Nora | `0975fe83-5ff2-51e1-86c6-79dd3e766b43.webp` |
| North | `ca7a8773-bf89-5a40-bea7-904e8103c46c.webp` |
| Orion | `e8cd64de-938f-561a-b230-f8f45005c9a6.webp` |
| Olive | `344798a3-2776-5ecc-9683-189b196e5d2c.webp` |
| Otis | `b45443ea-4a34-53f3-929a-99e5ce4779f0.webp` |
| Opal | `be15fe1c-dfa1-5a3a-b0f9-b01e6416c928.webp` |
| Onyx | `be9feb31-2360-5ecc-8ea6-351eeea4149d.webp` |
| Oona | `d8b6ecbc-305e-5c45-a45c-1699f1094b44.webp` |
| Sanchez | `81f40308-27c9-5d9a-82f1-7c4317727cc8.webp` |
| Sergio | `4caef1f4-0ea3-5896-ba0a-f8294016501d.webp` |
| Sampo | `62e1e83f-ccb1-53f8-8ed3-cb21243db22d.webp` |
| Sancho | `8e1bab41-e384-5d5b-b4a7-87453dfc2d9f.webp` |
| Siri | `c0c5f0d1-7a8c-569e-8e2c-71b5f059b457.webp` |
| Sophie | `01666ade-0cce-50da-aa31-57004729acee.webp` |
| Storm | `bdf70e56-7fb8-5638-b0ec-0210b324cabf.webp` |
| Sage | `ddd5579f-3c0d-5938-b99e-1ca24d459180.webp` |
| Taro | `41be6542-8265-537b-aa54-aade6547be13.webp` |
| Tessa | `186814a5-1082-5b3d-97bc-d3cc39cb7bae.webp` |
| Theo | `f79dc4e6-3be6-5823-af1e-148b359f5c4c.webp` |
| Tindra | `f5bd6d5c-e00a-5371-997b-b0935d8222ec.webp` |
| Toast | `c216a991-9c17-5ef9-a2f6-5a2debe9200f.webp` |
| Vega | `748a6bda-d09a-5642-825f-f5f1e0932d51.webp` |
| Valor | `510ac596-2611-5ae3-ab3b-add5a521f7b7.webp` |
| Violet | `d6e2c950-d166-5ca6-8f09-0a2297d68173.webp` |
| Viggo | `e515f2cd-3c13-50cf-9dfa-560f943255da.webp` |
| Viva | `ce31a653-6ef7-55cc-ba79-c8b647c13694.webp` |

## Integration and acceptance sequence

1. Generate and human-review each portrait against its manifest entry and the guide.
2. Put only the 60 exact filenames above in `frontend/public/media/dogs/` (the hidden
   `.gitkeep` may remain).
3. Run strict validation and inspect size outliers above 500 KB.
4. Confirm the canonical catalog derives `photo_key` as `<public-id>.webp` for all 60
   records. Media activation remains outside the independent domain semantic checksum.
5. Verify no request uses localhost or probes the server filesystem. The shared Angular
   component should render the deterministic relative URL, lazy-load lists, eagerly
   load the Profile hero, and fall back on any load error.
6. Run backend/frontend/database gates, then inspect Dogs, active/archived Profile, and
   Archive at 1440×1000, 768×900, and 390×844.
7. Perform the full human checklist for every image, with special review of the S, T,
   and V litters and all archived dogs.

For any replacement set, do not mark acceptance complete until every file, catalog
activation, automated check, and visual review passes.
