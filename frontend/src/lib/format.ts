/** A 0..1 score as a percentage. Near-certain scores read ">99%" and tiny ones "<1%", never "100%" or "0%". */
export const pct = (x: number) => (x > 0 && x < 0.01 ? '<1%' : x >= 0.995 && x < 1 ? '>99%' : `${Math.round(x * 100)}%`)
