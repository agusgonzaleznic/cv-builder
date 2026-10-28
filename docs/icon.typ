#set page(width: 512pt, height: 512pt, margin: 0pt, fill: rgb("#1d4f91"))
#place(top + left, dx: 106pt, dy: 76pt, rect(width: 250pt, height: 330pt, radius: 24pt, fill: white))
#for i in range(4) {
  place(top + left, dx: 146pt, dy: 136pt + i * 52pt,
        rect(width: (170pt, 170pt, 130pt, 150pt).at(i), height: 20pt, radius: 10pt, fill: rgb("#c4cfe0")))
}
#place(top + left, dx: 278pt, dy: 278pt, circle(radius: 82pt, fill: rgb("#1f7a47"), stroke: 14pt + white))
#let s = (paint: white, thickness: 26pt, cap: "round", join: "round")
#place(top + left, dx: 0pt, dy: 0pt, curve(stroke: s,
  curve.move((318pt, 362pt)), curve.line((350pt, 394pt)), curve.line((406pt, 330pt))))
