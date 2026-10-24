# IKEA KALAS source and geometry notes

Research date: 2026-10-24. Scope: bowl **603.786.69**, mug **403.786.70**, spoon **204.406.54**, plate **203.786.71**. These are identifiable product approximations for scene editing, not manufacturer CAD or metrology-grade digital twins.

## Official product measurements versus packaging

The measurements below were read from the requested IKEA Taiwan pages. Product and package sections are separate. Dimensions are in metres unless noted.

| Item | Official single-product measurement | Package-only measurement | Source |
| --- | --- | --- | --- |
| Bowl 603.786.69 | Diameter **0.120**; six bowls per pack | Stack height 0.090; package diameter 0.120; net pack weight 0.22 kg | [IKEA bowl](https://www.ikea.com.tw/en/products/children%27s-small-furniture-eat---study/baby-utensils-and-high-chair/kalas-art-60378669) |
| Mug 403.786.70 | Capacity **0.23 L = 0.000230 m³**; six cups per pack | Stack height 0.170; package diameter 0.080; net pack weight 0.19 kg | [IKEA mug](https://www.ikea.com.tw/en/products/children%27s-small-furniture-eat---study/baby-utensils-and-high-chair/kalas-art-40378670) |
| Spoon 204.406.54 | Length **0.160**; four spoons per pack | Package 0.220 × 0.110 × 0.020; net pack weight 0.06 kg | [IKEA spoon](https://www.ikea.com.tw/en/products/children%27s-small-furniture-eat---study/baby-utensils-and-high-chair/kalas-art-20440654) |
| Plate 203.786.71 | Diameter **0.190**; six plates per pack | Stack height 0.050; package diameter 0.190; net pack weight 0.32 kg | [IKEA plate](https://www.ikea.com.tw/en/products/children%27s-small-furniture-eat---study/baby-utensils-and-high-chair/kalas-art-20378671) |

**Do not use stack heights as object heights, package volume as liquid capacity, or pack weight as single-item mass.** Spoon 204.406.54 is the four-spoon product, not a generic 18-piece KALAS fork/knife/spoon set. The official pages list polypropylene plastic. Exact individual masses, thicknesses and sectional profiles were not provided.

## Supplemental dimensions

Dimensions.com publishes the following KALAS family measurements. These are secondary-source dimensions, not confirmation by IKEA for the exact Taiwan article numbers; use them as documented approximations until a physical sample is measured.

| Item | Diameter | Height | Source |
| --- | --- | --- | --- |
| Bowl | 0.120 | **0.046** | [Kalas Kids Bowl](https://www.dimensions.com/element/ikea-kalas-kids-bowl) |
| Tumbler | **0.080** | **0.081** | [Kalas Kids Tumbler](https://www.dimensions.com/element/ikea-kalas-kids-tumbler) |
| Plate | 0.190 | **0.024** | [Kalas Kids Plate](https://www.dimensions.com/element/ikea-kalas-kids-plate) |

## Visual evidence

These official product images were visually inspected in the browser. Images are references only; they are not copied into the distributed asset set.

- [Bowl photo](https://www.ikea.com.tw/dairyfarm/tw/images/980/0998009_PE822911_S5.webp): circular open bowl, outward-sloping wall, rounded transition into a broad nearly flat bottom, thin rounded rim; subdued pastel polypropylene.
- [Mug photo](https://www.ikea.com.tw/dairyfarm/tw/images/980/0998019_PE822917_S5.webp): **handleless** tapered tumbler, wider at the open rim, gently rounded base, thin wall. The word “mug” must not introduce a handle.
- [Plate photo](https://www.ikea.com.tw/dairyfarm/tw/images/980/0998030_PE822920_S5.webp): broad circular flat well with a shallow raised, slightly outward-flared rim and soft corner transition. Not a flat solid disc or a deep bowl. Concentric moulded marks are visible on the well.
- [Spoon front view](https://www.ikea.com.tw/dairyfarm/tw/images/477/1047763_PE843511_S5.webp) and [oblique view](https://www.ikea.com.tw/dairyfarm/tw/images/477/1047762_PE843512_S5.webp): elongated oval/teardrop concave head, narrow neck, long handle widening toward a rounded butt, shallow embossed decoration. The head joins the neck smoothly, with no sharp cylindrical stem.

The spoon front view has an approximately 665-pixel end-to-end silhouette and 135-pixel maximum head width at the inspected display size: 0.160 × 135/665 ≈ **0.0325 m**. Perspective, rounding and image framing limit this estimate; do not present it as an official width. The head-to-neck transition occupies approximately 0.055–0.060 m of its length; handle butt width is approximately 0.022 m.

## Search for existing reusable 3D models

Searches were performed before recommending new geometry: “IKEA KALAS bowl cup spoon plate 3D model license”, a targeted KALAS/3D search, “IKEA KALAS 3D Printed”, and “KALAS Spoon 3d model”. Results were inspected directly where available. This is a bounded search, not proof that no permissively licensed model exists anywhere.

| Candidate | Observed availability / license | Decision for this project |
| --- | --- | --- |
| [KALAS Spoon by D3DIdeal](https://www.cgtrader.com/3d-models/furniture/other/kalas-spoon), model 5309750 | Paid purchase/subscription; OBJ, FBX, glTF, STL, 3DS, USDZ listed. Page explicitly labels **Royalty Free License (no AI)** and 52,434 polygons. No exact article-number match established. | Not acquired or bundled. Purchase and license review would be needed; listing is not evidence of permission to redistribute an editable source asset or use it in robotics training. |
| [KALAS bowl replacement by MD Design, via its Yeggi result](https://m.yeggi.com/goto/l5ueoXN6ZqrisbLb0JqXktG1xqe6wvbxquPi9qPj4PDa2ujq2ayTo7Gm0dfY4drarqpj1dWiZdfTZKPhyrnGuXZ4raqsoJmsn_DNodzP1afZ2tPpcbPHn93L2ZW2taPZk5yr25Kcm5_ZuL6ndL/j46fQ0d/TlM/V3sfn) | The redirected MakerWorld page was scraped and inspected: title “IKEA Storage Bowl 3D Printed (Same Size)/IKEA KALAS Bowl 3D Printed (Same Size”, released 2026-02-05. Author claims matching key dimensions; page labels **Standard Digital File License**. | Not acquired or bundled. “Free download” does not establish redistribution permission. Public description did not give numeric dimensions or certify the requested article. |
| [Dimensions.com bowl](https://www.dimensions.com/element/ikea-kalas-kids-bowl), [tumbler](https://www.dimensions.com/element/ikea-kalas-kids-tumbler), [plate](https://www.dimensions.com/element/ikea-kalas-kids-plate) | Product-specific drawings and 3D previews. Bowl/tumbler pages state 3D downloads require **Dimensions Pro**, with 3DM/SKP/OBJ formats where available. Plate shows a 3D preview. No permissive redistribution license established. | Use the public dimensional facts as supplemental references, not downloaded mesh files. No subscription, purchase or asset download performed. |
| [Printables KALAS results](https://www.printables.com/search/models?q=tag%3Akalas), [Yeggi KALAS results](https://m.yeggi.com/q/ikea+kalas/) | Predominantly accessories: cup/bowl lids, holders, risers, organisers. Search-index “free” labels are not licenses. | No exact, reusable four-item set verified. Accessory geometry is not a substitute for the requested objects. |

**Recommended fallback:** independently author simple procedural geometry from the official measurements and observed shape. Do not label those meshes as downloaded IKEA CAD or exact scans. No external mesh files or product images were imported during this research.

## Recommended initial geometry in SI units

Only values explicitly marked official above are manufacturer-published single-product measurements. Every other parameter below is a starting approximation, including those supported by Dimensions.com. Keep the parameters easy to replace after physical measurement.

| Item | Recommended envelope | Suggested sectional parameters | Evidence status |
| --- | --- | --- | --- |
| Bowl | Diameter 0.120; height 0.046 | Bottom diameter about 0.090–0.095; wall about 0.002; floor about 0.0025; smooth bottom corner radius about 0.006–0.010 | Diameter official; height secondary; bottom/thickness/curvature inferred from photos and modelling judgement |
| Tumbler | Rim diameter 0.080; height 0.081; no handle | Bottom diameter about 0.060; wall about 0.0015–0.002; floor about 0.0025; smooth base corner | Envelope secondary and consistent with package diameter; remaining dimensions inferred. Capacity 230 mL official, but do not assume brimful capacity is exactly nominal capacity |
| Plate | Diameter 0.190; total height 0.024 | Flat well diameter about 0.155–0.160; bottom/floor thickness about 0.0025; rim wall about 0.002; rounded well-to-rim transition | Diameter official; height secondary; internal geometry inferred |
| Spoon | End-to-end length 0.160; head width about 0.0325 | Head-to-neck region about 0.055–0.060 long; handle butt about 0.022 wide; neck about 0.012 wide; shell about 0.002; head depression about 0.006; total vertical envelope about 0.010–0.012 | Length official; plan proportions photo-derived; depth, thickness and bend are modelling assumptions |

For editor display, use names such as “IKEA KALAS bowl (approx.)” and expose the article number/source where practical. A scalar size control should preserve the default physical proportions; separate axes may be offered only when clearly labelled as shape changes. Render open interiors. If physics uses simplified convex pieces, record that collision geometry is an approximation separate from the visible surface. Do not silently fill the bowl/cup/plate cavity with a single convex hull when containment matters.

Unknowns needing a physical sample or manufacturer drawing: true wall/floor thickness, underside recess and foot dimensions, rim bead, spoon scoop depth and bend, individual object mass, friction and compliance. Pack-average mass can be an initial estimate but is not an individual measured mass. This document provides geometry references, not validated contact dynamics.

## Implemented defaults

The current reconstruction uses bowl Ø120 × 46 mm, cup Ø80 × 81 mm, plate Ø190 × 24 mm, spoon 160 × 33 × 8 mm. Spoon width is rounded from the photographic estimate and its 8 mm vertical envelope is a modelling choice. Container walls/floors use approximately 2 mm, with faceted convex collision pieces and a smoother visual shell. Approximate masses are bowl 45 g, cup 30 g, plate 65 g, spoon 9 g; these are simulation parameters, not measured individual-item weights. Inspector controls can calibrate mass, friction and scale after measurement.
