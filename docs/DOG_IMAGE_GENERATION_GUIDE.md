# Synthetic dog image generation guide

This guide is the shared P10 visual contract. P10A contains **no dog photographs**.
P10B must generate every final image from the fictional identity in
[`dog-media-manifest.json`](dog-media-manifest.json), review it, and place it under the
single public media directory. No real kennel, stock, scraped, or reference-repository
photograph may be used as an input, style reference, test fixture, or final asset.

## Output contract

- manifest version: `dog-media-v1`;
- one image for each of exactly 60 canonical dogs;
- WebP, exactly `1086 × 1448 px`, portrait `3:4`;
- filename exactly `<dog-public-uuid>.webp` from the manifest;
- repository directory: `frontend/public/media/dogs/`;
- public URL: `/media/dogs/<filename>?v=dog-media-v1`;
- typical target below 300 KB; every file above 500 KB requires explicit quality/size
  review.

The UUID filename owns identity independently of display order or name. Do not create
manual thumbnails, alternate crops, galleries, or archived-dog subdirectories.

## Shared photographic language

Use realistic modern outdoor dog photography: one northern working sled dog, fully
visible from ears through every paw and the complete tail, standing or calmly posed on
textured snow. Use soft northern daylight, natural color, believable depth, and a
restrained winter landscape. Backgrounds should feel like one fictional kennel during
one winter without being pixel-identical.

The dog remains the clear subject. Paws must contact textured snow naturally; snow may
not become a white studio floor, glowing void, smeared cut-out, or blurred paint. A
simple unbranded collar is acceptable, but the default is no accessory.

Never include:

- people, a second dog, leash, sled harness, equipment, branding, text, watermark,
  border, or UI decoration;
- cropped feet, preventable tail cropping, duplicate or merged limbs, malformed paws,
  incorrect ears, unnatural eyes, damaged muzzle, or implausible anatomy;
- illustration, painting, cartoon, fantasy, 3D-render, poster, or exaggerated HDR
  treatment;
- studio, indoor kennel, city, tropical, or other incoherent setting.

## Identity and inheritance

The manifest is authoritative for coat, face, eyes, build, ears, tail, apparent age,
distinctive mark, and portrait character. It also supplies a concise complete prompt.
Do not normalize every dog into a blue-eyed show-breed Siberian Husky. The population
should read as varied northern working dogs: lean Alaskan-husky-like builds alongside
denser coats, with brown, amber, hazel, blue, and occasional mixed eyes.

The visual inheritance plan is modest and reviewable:

- Aurora begins a silver-grey/open-face line visible through C and H descendants;
- Atlas contributes dark coats and broader structure through D and K;
- Freya carries copper/red and ivory markings through D and M;
- Fjord contributes charcoal agouti, dense coat, and masked faces through H and N;
- later crosses combine those cues rather than copying one parent exactly;
- littermates share a family palette or facial structure but retain a unique marking,
  eye treatment, build, and pose.

The S-litter must look related without becoming eight clones. T puppies are about 11
weeks old on the reference date; V puppies are about 6 weeks old and should look
subtly younger. Juniors look adolescent/yearling, mature workers look adult, and 2016
foundation dogs may show restrained muzzle silvering without frailty. Archived dogs
are portrayed as healthy dogs at a plausible life stage; archive reason must never be
depicted.

## Generation process for P10B

1. Read the shared rules in this guide and one manifest entry.
2. Generate from that entry's `generation_brief`; the dog's name is an identity label,
   not text to render in the image.
3. Export the selected result directly as target-size WebP where the generator permits.
4. Reject and regenerate anatomy, age, composition, snow-contact, identity, or privacy
   failures rather than repairing them with unrelated source photography.
5. Save under the exact UUID filename in `frontend/public/media/dogs/`.
6. Run the structural validator and then complete human QA for every file.
7. Activate validated files through the existing nullable `Dog.photo_key` catalog
   contract in one reviewed change; never probe the filesystem from each API response.

## Human visual QA checklist

Review each image at full size and in Registry, Profile, and Archive contexts:

- manifest identity, sex, and apparent age match;
- exactly one dog; full body, four correct legs, natural paws, correct ears and tail;
- no duplicated/merged limbs, malformed muzzle, eye artifact, or extra animal;
- believable paw/snow contact and natural textured snow;
- no person, text, logo, watermark, frame, leash, harness, or branded equipment;
- background and lighting belong to the common winter world;
- dog remains distinct from its siblings while family resemblance is credible;
- Profile crop is strong and Registry/Archive crops preserve identity;
- image is sharp enough for the hero, not obviously synthetic, and within the size
  budget or has a documented reason.

The automated validator checks ownership, container structure, exact dimensions, and
file sizes. It intentionally cannot approve anatomy, visual fidelity, or privacy; human
review is a hard P10B gate.
