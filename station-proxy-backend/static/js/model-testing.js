// Purpose: Render the Model & Testing tab, keeping its long-form copy out of index.html.

// The content is static trusted markup (no artifact- or user-derived strings),
// so it is safe to inject directly. Every number below is measured from a run
// artifact or manifest; the sources are listed in the final section, and
// weather_reconstruction_model/MODEL_RUNS.md is the source of truth. The chart
// figures are static SVG with bar/curve geometry computed from the holdout
// master and the row-locked baseline comparison artifacts.

// How one daily estimate is assembled (inputs -> features -> forest -> offset + baseline).
const MODEL_FLOW_DIAGRAM_SVG = `<svg viewBox="0 0 760 350" role="img" aria-label="How one daily estimate is assembled: station and terrain inputs feed 873 features into a random forest that predicts an offset added to a regional hub baseline" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><defs><marker id="mtflow-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker></defs><rect x="8" y="30" width="182" height="46" rx="8" fill="#eff6ff" stroke="#93c5fd" stroke-width="1.5"/><text x="99.0" y="48" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">5 hub stations</text><text x="99.0" y="66" text-anchor="middle" fill="#64748b" font-size="11">long-record anchors</text><rect x="8" y="92" width="182" height="46" rx="8" fill="#eff6ff" stroke="#93c5fd" stroke-width="1.5"/><text x="99.0" y="110" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">10 neighbor stations</text><text x="99.0" y="128" text-anchor="middle" fill="#64748b" font-size="11">nearby target records</text><rect x="8" y="154" width="182" height="46" rx="8" fill="#eff6ff" stroke="#93c5fd" stroke-width="1.5"/><text x="99.0" y="172" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">Terrain features (DEM)</text><text x="99.0" y="190" text-anchor="middle" fill="#64748b" font-size="11">elevation - slope - relief</text><rect x="8" y="216" width="182" height="46" rx="8" fill="#eff6ff" stroke="#93c5fd" stroke-width="1.5"/><text x="99.0" y="234" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">Seasonality</text><text x="99.0" y="252" text-anchor="middle" fill="#64748b" font-size="11">day-of-year encoding</text><line x1="190" y1="53" x2="249" y2="118" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><line x1="190" y1="115" x2="249" y2="140" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><line x1="190" y1="177" x2="249" y2="162" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><line x1="190" y1="239" x2="249" y2="184" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><rect x="252" y="96" width="142" height="110" rx="10" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/><text x="323.0" y="146" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">873</text><text x="323.0" y="164" text-anchor="middle" fill="#64748b" font-size="11">features per day</text><line x1="394" y1="151" x2="443" y2="151" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><rect x="446" y="110" width="158" height="82" rx="10" fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"/><text x="525.0" y="146" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">Random forest</text><text x="525.0" y="164" text-anchor="middle" fill="#64748b" font-size="11">300 trees - depth &#8804; 20</text><line x1="604" y1="151" x2="645" y2="151" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><rect x="648" y="117" width="104" height="68" rx="8" fill="#fef9c3" stroke="#fde047" stroke-width="1.5"/><text x="700.0" y="146" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">Predicted</text><text x="700.0" y="164" text-anchor="middle" fill="#64748b" font-size="11">local offset</text><rect x="252" y="272" width="190" height="48" rx="8" fill="#ccfbf1" stroke="#5eead4" stroke-width="1.5"/><text x="347.0" y="291" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">Regional hub baseline</text><text x="347.0" y="309" text-anchor="middle" fill="#64748b" font-size="11">average of the 5 hubs</text><polyline points="700,185 700,232 490,232 490,276" fill="none" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><circle cx="490" cy="296" r="15" fill="#ffffff" stroke="#64748b" stroke-width="1.5"/><line x1="483" y1="296" x2="497" y2="296" stroke="#334155" stroke-width="2"/><line x1="490" y1="289" x2="490" y2="303" stroke="#334155" stroke-width="2"/><line x1="442" y1="296" x2="471" y2="296" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><line x1="505" y1="296" x2="533" y2="296" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtflow-arrow)"/><rect x="536" y="272" width="216" height="48" rx="8" fill="#dcfce7" stroke="#86efac" stroke-width="1.5"/><text x="644.0" y="291" text-anchor="middle" fill="#166534" font-size="13" font-weight="bold">Reconstructed daily</text><text x="644.0" y="309" text-anchor="middle" fill="#64748b" font-size="11">temperature (TAVG / TMIN / TMAX)</text></svg>`;

// The grouped-holdout cycle: hold out a station group, train on the rest, score the group.
const HOLDOUT_SCHEMATIC_SVG = `<svg viewBox="0 0 760 252" role="img" aria-label="Grouped station holdout: hold out one group of stations, train on all the rest, then score the held-out stations on their real days; repeated 189 times" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><defs><marker id="mtho-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/></marker></defs><rect x="8" y="38" width="225" height="190" rx="10" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/><text x="120" y="26" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">1 - Hold out one group</text><rect x="268" y="38" width="225" height="190" rx="10" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/><text x="380" y="26" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">2 - Train on everyone else</text><rect x="528" y="38" width="225" height="190" rx="10" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/><text x="640" y="26" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">3 - Score the held-out stations</text><line x1="233" y1="133" x2="265" y2="133" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtho-arrow)"/><line x1="493" y1="133" x2="525" y2="133" stroke="#64748b" stroke-width="1.5" marker-end="url(#mtho-arrow)"/><circle cx="38" cy="78" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="70" cy="78" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="102" cy="78" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="134" cy="78" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="166" cy="78" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="198" cy="78" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="38" cy="110" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="70" cy="110" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="102" cy="110" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="134" cy="110" r="7" fill="#fecaca" stroke="#dc2626" stroke-width="2"/><circle cx="166" cy="110" r="7" fill="#fecaca" stroke="#dc2626" stroke-width="2"/><circle cx="198" cy="110" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="38" cy="142" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="70" cy="142" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="102" cy="142" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="134" cy="142" r="7" fill="#fecaca" stroke="#dc2626" stroke-width="2"/><circle cx="166" cy="142" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="198" cy="142" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="38" cy="174" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="70" cy="174" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="102" cy="174" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="134" cy="174" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="166" cy="174" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><circle cx="198" cy="174" r="7" fill="#93c5fd" stroke="#3b82f6" stroke-width="1.5"/><text x="120" y="212" text-anchor="middle" fill="#b91c1c" font-size="11" font-weight="bold">red = group of 2&#8211;5 stations, fully removed</text><rect x="296" y="92" width="170" height="64" rx="10" fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"/><text x="381.0" y="119" text-anchor="middle" fill="#1e293b" font-size="13" font-weight="bold">Random forest</text><text x="381.0" y="137" text-anchor="middle" fill="#64748b" font-size="11">group fully excluded</text><text x="381" y="182" text-anchor="middle" fill="#64748b" font-size="11">trained on all remaining stations</text><text x="381" y="198" text-anchor="middle" fill="#64748b" font-size="11">(~1.65M daily rows per fit)</text><line x1="556" y1="150" x2="716" y2="150" stroke="#94a3b8"/><line x1="556" y1="74" x2="556" y2="150" stroke="#94a3b8"/><polyline points="560,120 580,100 600,110 620,88 640,98 660,80 680,92 700,84" fill="none" stroke="#2563eb" stroke-width="2"/><polyline points="560,126 580,107 600,115 620,95 640,103 660,87 680,97 700,89" fill="none" stroke="#dc2626" stroke-width="2"/><text x="640" y="182" text-anchor="middle" fill="#64748b" font-size="11">predicted vs real observed days</text><text x="640" y="198" text-anchor="middle" fill="#64748b" font-size="11">MAE - RMSE - r recorded per station</text></svg>`;

// Distribution of the 189 measured group-fit training times.
const FIT_TIME_HISTOGRAM_SVG = `<svg viewBox="0 0 760 300" role="img" aria-label="Distribution of the 189 grouped-holdout training times in minutes" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><line x1="52" y1="254.0" x2="742" y2="254.0" stroke="#e2e8f0"/><text x="44" y="258.0" text-anchor="end" fill="#64748b" font-size="12">0</text><line x1="52" y1="213.3" x2="742" y2="213.3" stroke="#e2e8f0"/><text x="44" y="217.3" text-anchor="end" fill="#64748b" font-size="12">20</text><line x1="52" y1="172.5" x2="742" y2="172.5" stroke="#e2e8f0"/><text x="44" y="176.5" text-anchor="end" fill="#64748b" font-size="12">40</text><line x1="52" y1="131.8" x2="742" y2="131.8" stroke="#e2e8f0"/><text x="44" y="135.8" text-anchor="end" fill="#64748b" font-size="12">60</text><line x1="52" y1="91.1" x2="742" y2="91.1" stroke="#e2e8f0"/><text x="44" y="95.1" text-anchor="end" fill="#64748b" font-size="12">80</text><line x1="52" y1="50.4" x2="742" y2="50.4" stroke="#e2e8f0"/><text x="44" y="54.4" text-anchor="end" fill="#64748b" font-size="12">100</text><rect x="123.0" y="203.1" width="65.0" height="50.9" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="399.0" y="174.6" width="65.0" height="79.4" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="468.0" y="38.1" width="65.0" height="215.9" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="537.0" y="243.8" width="65.0" height="10.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="606.0" y="245.9" width="65.0" height="8.1" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="675.0" y="233.6" width="65.0" height="20.4" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="52.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">0</text><text x="190.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">30</text><text x="328.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">60</text><text x="466.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">90</text><text x="604.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">120</text><text x="742.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">150</text><line x1="477.2" y1="30" x2="477.2" y2="254" stroke="#2563eb" stroke-width="2" stroke-dasharray="5 4"/><text x="471.2" y="46" text-anchor="end" fill="#2563eb" font-size="13" font-weight="bold">median 92 min</text><text x="397" y="292" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">Training time per grouped-holdout fit (minutes, 48-core node)</text><text x="16" y="142" text-anchor="middle" transform="rotate(-90 16 142)" fill="#475569" font-size="13" font-weight="bold">Fits</text></svg>`;

// Cumulative share of stations by holdout MAE: model vs the row-locked baselines.
const BASELINE_CDF_SVG = `<svg viewBox="0 0 760 320" role="img" aria-label="Cumulative share of stations by holdout MAE: model vs IDW vs nearest hub" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><line x1="52" y1="274.0" x2="742" y2="274.0" stroke="#e2e8f0"/><text x="44" y="278.0" text-anchor="end" fill="#64748b" font-size="12">0%</text><line x1="52" y1="213.0" x2="742" y2="213.0" stroke="#e2e8f0"/><text x="44" y="217.0" text-anchor="end" fill="#64748b" font-size="12">25%</text><line x1="52" y1="152.0" x2="742" y2="152.0" stroke="#e2e8f0"/><text x="44" y="156.0" text-anchor="end" fill="#64748b" font-size="12">50%</text><line x1="52" y1="91.0" x2="742" y2="91.0" stroke="#e2e8f0"/><text x="44" y="95.0" text-anchor="end" fill="#64748b" font-size="12">75%</text><line x1="52" y1="30.0" x2="742" y2="30.0" stroke="#e2e8f0"/><text x="44" y="34.0" text-anchor="end" fill="#64748b" font-size="12">100%</text><text x="52.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">0</text><text x="224.5" y="294" text-anchor="middle" fill="#64748b" font-size="12">2</text><text x="397.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">4</text><text x="569.5" y="294" text-anchor="middle" fill="#64748b" font-size="12">6</text><text x="742.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">8</text><path d="M52.0,274.0 L52.0,273.7 L160.2,272.3 L178.2,271.0 L192.3,269.7 L197.7,268.4 L200.7,267.1 L207.6,265.7 L215.0,264.4 L221.7,263.1 L226.9,261.8 L233.4,260.5 L235.6,259.1 L243.3,257.8 L249.7,256.5 L253.1,255.2 L259.4,253.9 L263.5,252.5 L265.9,251.2 L268.7,249.9 L274.0,248.6 L277.9,247.3 L280.3,245.9 L284.2,244.6 L287.4,243.3 L289.0,242.0 L292.8,240.7 L294.3,239.3 L298.7,238.0 L302.9,236.7 L305.9,235.4 L307.5,234.0 L309.9,232.7 L311.1,231.4 L313.9,230.1 L315.7,228.8 L318.5,227.4 L321.9,226.1 L327.1,224.8 L331.7,223.5 L333.1,222.2 L334.7,220.8 L337.1,219.5 L339.2,218.2 L340.0,216.9 L341.6,215.6 L344.1,214.2 L346.0,212.9 L349.6,211.6 L351.1,210.3 L351.9,209.0 L356.6,207.6 L359.8,206.3 L363.0,205.0 L364.0,203.7 L366.4,202.4 L367.1,201.0 L369.9,199.7 L372.1,198.4 L372.9,197.1 L375.9,195.7 L379.6,194.4 L380.8,193.1 L383.2,191.8 L386.0,190.5 L390.8,189.1 L394.4,187.8 L397.4,186.5 L398.9,185.2 L402.0,183.9 L404.9,182.5 L408.4,181.2 L410.1,179.9 L413.8,178.6 L416.9,177.3 L421.0,175.9 L422.8,174.6 L424.1,173.3 L425.3,172.0 L428.3,170.7 L430.3,169.3 L432.0,168.0 L436.3,166.7 L438.7,165.4 L440.3,164.1 L443.0,162.7 L443.9,161.4 L446.1,160.1 L450.7,158.8 L451.9,157.4 L454.6,156.1 L458.3,154.8 L460.0,153.5 L462.8,152.2 L465.7,150.8 L468.4,149.5 L469.8,148.2 L474.8,146.9 L479.3,145.6 L482.8,144.2 L486.2,142.9 L489.4,141.6 L493.2,140.3 L494.4,139.0 L496.0,137.6 L498.8,136.3 L501.7,135.0 L508.4,133.7 L509.1,132.4 L510.9,131.0 L511.6,129.7 L513.2,128.4 L515.7,127.1 L517.5,125.8 L520.3,124.4 L525.6,123.1 L528.8,121.8 L531.5,120.5 L532.9,119.1 L535.4,117.8 L541.4,116.5 L544.0,115.2 L555.2,113.9 L557.1,112.5 L558.8,111.2 L559.8,109.9 L561.7,108.6 L566.5,107.3 L570.8,105.9 L573.1,104.6 L577.7,103.3 L582.1,102.0 L587.9,100.7 L597.2,99.3 L606.9,98.0 L612.9,96.7 L614.6,95.4 L621.9,94.1 L624.3,92.7 L633.3,91.4 L643.3,90.1 L654.4,88.8 L663.0,87.5 L676.5,86.1 L683.7,84.8 L688.2,83.5 L694.9,82.2 L696.6,80.8 L709.2,79.5 L723.3,78.2 L729.5,76.9 L737.0,75.6 L742.0,74.2 L742.0,72.9 L742.0,71.6 L742.0,70.3 L742.0,69.0 L742.0,67.6 L742.0,66.3 L742.0,65.0 L742.0,63.7 L742.0,62.4 L742.0,61.0 L742.0,59.7 L742.0,58.4 L742.0,57.1 L742.0,55.8 L742.0,54.4 L742.0,53.1 L742.0,51.8 L742.0,50.5 L742.0,49.2 L742.0,47.8 L742.0,46.5 L742.0,45.2 L742.0,43.9 L742.0,42.5 L742.0,41.2 L742.0,39.9 L742.0,38.6 L742.0,37.3 L742.0,35.9 L742.0,34.6 L742.0,33.3 L742.0,32.0 L742.0,30.7 L742.0,30.0" fill="none" stroke="#dc2626" stroke-width="3" stroke-linejoin="round"/><path d="M52.0,274.0 L54.9,273.7 L150.8,272.3 L175.5,271.0 L181.9,269.7 L189.6,268.4 L196.3,267.1 L198.7,265.7 L201.3,264.4 L207.6,263.1 L214.6,261.8 L218.4,260.5 L222.0,259.1 L226.8,257.8 L230.0,256.5 L232.5,255.2 L233.9,253.9 L239.1,252.5 L241.8,251.2 L244.9,249.9 L247.2,248.6 L251.0,247.3 L257.6,245.9 L262.5,244.6 L264.9,243.3 L266.3,242.0 L270.3,240.7 L272.9,239.3 L274.0,238.0 L275.2,236.7 L278.5,235.4 L280.8,234.0 L282.9,232.7 L283.5,231.4 L285.9,230.1 L287.8,228.8 L289.6,227.4 L290.4,226.1 L291.1,224.8 L294.4,223.5 L295.7,222.2 L298.6,220.8 L303.4,219.5 L305.8,218.2 L306.8,216.9 L309.4,215.6 L311.8,214.2 L313.5,212.9 L316.0,211.6 L318.1,210.3 L321.2,209.0 L324.0,207.6 L324.5,206.3 L325.8,205.0 L327.9,203.7 L330.9,202.4 L331.7,201.0 L332.5,199.7 L336.4,198.4 L339.7,197.1 L340.9,195.7 L342.8,194.4 L345.1,193.1 L348.9,191.8 L350.4,190.5 L352.2,189.1 L354.6,187.8 L358.1,186.5 L359.9,185.2 L361.0,183.9 L363.8,182.5 L366.1,181.2 L367.1,179.9 L368.8,178.6 L371.4,177.3 L374.0,175.9 L375.2,174.6 L376.2,173.3 L378.7,172.0 L380.3,170.7 L381.3,169.3 L384.0,168.0 L386.5,166.7 L388.5,165.4 L390.2,164.1 L393.0,162.7 L394.3,161.4 L395.9,160.1 L397.7,158.8 L401.0,157.4 L405.7,156.1 L408.2,154.8 L412.6,153.5 L416.7,152.2 L420.6,150.8 L422.3,149.5 L422.7,148.2 L425.9,146.9 L429.1,145.6 L432.2,144.2 L434.8,142.9 L435.7,141.6 L440.1,140.3 L443.3,139.0 L445.0,137.6 L447.0,136.3 L450.1,135.0 L451.5,133.7 L453.2,132.4 L454.7,131.0 L456.7,129.7 L457.2,128.4 L459.6,127.1 L466.1,125.8 L468.8,124.4 L470.2,123.1 L472.3,121.8 L473.3,120.5 L477.3,119.1 L480.1,117.8 L482.4,116.5 L485.4,115.2 L491.7,113.9 L493.5,112.5 L501.9,111.2 L509.2,109.9 L516.3,108.6 L523.0,107.3 L526.0,105.9 L531.1,104.6 L534.6,103.3 L543.2,102.0 L556.3,100.7 L563.0,99.3 L565.0,98.0 L574.9,96.7 L584.3,95.4 L587.9,94.1 L593.4,92.7 L596.3,91.4 L599.0,90.1 L601.9,88.8 L608.1,87.5 L611.9,86.1 L617.5,84.8 L625.1,83.5 L635.8,82.2 L639.8,80.8 L643.4,79.5 L646.1,78.2 L659.2,76.9 L664.1,75.6 L672.5,74.2 L678.0,72.9 L698.0,71.6 L707.5,70.3 L714.5,69.0 L731.0,67.6 L740.3,66.3 L742.0,65.0 L742.0,63.7 L742.0,62.4 L742.0,61.0 L742.0,59.7 L742.0,58.4 L742.0,57.1 L742.0,55.8 L742.0,54.4 L742.0,53.1 L742.0,51.8 L742.0,50.5 L742.0,49.2 L742.0,47.8 L742.0,46.5 L742.0,45.2 L742.0,43.9 L742.0,42.5 L742.0,41.2 L742.0,39.9 L742.0,38.6 L742.0,37.3 L742.0,35.9 L742.0,34.6 L742.0,33.3 L742.0,32.0 L742.0,30.7 L742.0,30.0" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linejoin="round"/><path d="M52.0,274.0 L136.5,273.7 L153.1,272.3 L157.6,271.0 L161.8,269.7 L163.4,268.4 L166.0,267.1 L169.0,265.7 L170.9,264.4 L172.5,263.1 L174.0,261.8 L177.4,260.5 L177.8,259.1 L179.0,257.8 L180.5,256.5 L182.2,255.2 L183.3,253.9 L185.5,252.5 L186.3,251.2 L187.0,249.9 L188.8,248.6 L190.0,247.3 L190.9,245.9 L191.9,244.6 L193.1,243.3 L194.1,242.0 L195.5,240.7 L195.8,239.3 L197.2,238.0 L197.7,236.7 L199.2,235.4 L199.7,234.0 L200.0,232.7 L201.5,231.4 L202.5,230.1 L204.0,228.8 L205.6,227.4 L206.9,226.1 L207.5,224.8 L208.2,223.5 L208.4,222.2 L208.9,220.8 L209.9,219.5 L211.0,218.2 L211.5,216.9 L212.0,215.6 L212.8,214.2 L214.4,212.9 L215.3,211.6 L217.1,210.3 L218.6,209.0 L219.0,207.6 L219.6,206.3 L222.4,205.0 L223.6,203.7 L224.5,202.4 L225.1,201.0 L225.7,199.7 L228.5,198.4 L229.0,197.1 L230.3,195.7 L231.0,194.4 L232.7,193.1 L233.2,191.8 L234.0,190.5 L234.7,189.1 L235.1,187.8 L236.0,186.5 L237.8,185.2 L238.8,183.9 L239.8,182.5 L241.8,181.2 L242.5,179.9 L243.6,178.6 L244.1,177.3 L244.8,175.9 L246.1,174.6 L246.8,173.3 L247.5,172.0 L248.4,170.7 L249.1,169.3 L249.6,168.0 L250.8,166.7 L251.9,165.4 L254.2,164.1 L255.0,162.7 L255.9,161.4 L256.5,160.1 L257.4,158.8 L259.0,157.4 L260.8,156.1 L261.3,154.8 L262.9,153.5 L265.9,152.2 L266.6,150.8 L266.9,149.5 L267.8,148.2 L268.5,146.9 L269.4,145.6 L271.1,144.2 L271.9,142.9 L274.5,141.6 L275.4,140.3 L277.3,139.0 L277.9,137.6 L279.1,136.3 L279.9,135.0 L281.6,133.7 L282.0,132.4 L282.7,131.0 L283.8,129.7 L284.7,128.4 L285.5,127.1 L286.4,125.8 L287.0,124.4 L289.5,123.1 L290.8,121.8 L291.4,120.5 L293.6,119.1 L295.2,117.8 L297.9,116.5 L302.3,115.2 L304.3,113.9 L304.7,112.5 L305.9,111.2 L306.2,109.9 L307.9,108.6 L309.1,107.3 L310.7,105.9 L312.9,104.6 L313.7,103.3 L315.0,102.0 L316.0,100.7 L318.6,99.3 L319.4,98.0 L320.4,96.7 L324.6,95.4 L326.2,94.1 L326.8,92.7 L328.6,91.4 L330.9,90.1 L331.5,88.8 L335.7,87.5 L338.0,86.1 L341.5,84.8 L344.0,83.5 L346.1,82.2 L347.3,80.8 L348.4,79.5 L349.9,78.2 L351.5,76.9 L353.3,75.6 L355.9,74.2 L358.2,72.9 L360.3,71.6 L361.4,70.3 L366.1,69.0 L368.3,67.6 L369.7,66.3 L371.3,65.0 L373.3,63.7 L376.7,62.4 L380.7,61.0 L383.8,59.7 L387.1,58.4 L388.1,57.1 L391.4,55.8 L396.7,54.4 L400.7,53.1 L405.1,51.8 L418.3,50.5 L424.0,49.2 L429.4,47.8 L432.8,46.5 L442.8,45.2 L443.2,43.9 L447.8,42.5 L453.3,41.2 L457.2,39.9 L465.0,38.6 L484.7,37.3 L504.9,35.9 L535.6,34.6 L562.9,33.3 L598.1,32.0 L694.4,30.7 L742.0,30.0" fill="none" stroke="#2563eb" stroke-width="3" stroke-linejoin="round"/><line x1="266.4" y1="152.0" x2="266.4" y2="274" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="4 4"/><circle cx="266.4" cy="152.0" r="4.5" fill="#2563eb" stroke="#fff" stroke-width="2"/><text x="278.4" y="174.0" fill="#2563eb" font-size="13" font-weight="bold">half the stations under 2.49 F</text><line x1="502" y1="150" x2="528" y2="150" stroke="#2563eb" stroke-width="3"/><text x="536" y="154" fill="#475569" font-size="13">Paloma v1</text><line x1="502" y1="170" x2="528" y2="170" stroke="#f59e0b" stroke-width="3"/><text x="536" y="174" fill="#475569" font-size="13">IDW of 5 hubs</text><line x1="502" y1="190" x2="528" y2="190" stroke="#dc2626" stroke-width="3"/><text x="536" y="194" fill="#475569" font-size="13">Nearest hub</text><text x="397" y="312" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">Station holdout MAE (F)</text><text x="16" y="152" text-anchor="middle" transform="rotate(-90 16 152)" fill="#475569" font-size="13" font-weight="bold">Share of stations at or below</text></svg>`;

const MODEL_TESTING_HTML = `
    <h2>Model &amp; Testing</h2>
    <p class="methodology-intro">
        Paloma v1 reconstructs daily temperatures for weather stations with missing or
        incomplete records. It learns how each station's temperatures relate to nearby
        long-record stations and the surrounding terrain, then uses those relationships to
        estimate what the station would have measured on any given day. The rest of this page
        gets specific: how the model is put together, how it was tested, where the computing
        happened, and how long it took. Every number is measured from a saved run artifact,
        and the sources are listed at the bottom.
    </p>

    <div class="station-glance-grid testing-headline">
        <div class="station-glance-card">
            <div class="station-glance-label">Validation Stations</div>
            <div class="station-glance-value">739</div>
            <div class="station-glance-detail">Every eligible station the model trains on. Each was scored by a forest trained with that station completely removed.</div>
        </div>
        <div class="station-glance-card">
            <div class="station-glance-label">Held-Out Station Days</div>
            <div class="station-glance-value">416,892</div>
            <div class="station-glance-detail">Each one is a single day at a single station: the model's estimate checked against the temperature actually recorded that day.</div>
        </div>
        <div class="station-glance-card">
            <div class="station-glance-label">Mean Station MAE</div>
            <div class="station-glance-value">2.68 F</div>
            <div class="station-glance-detail">The average of each station's daily error (TAVG). The median station comes in at 2.49 F.</div>
        </div>
        <div class="station-glance-card">
            <div class="station-glance-label">Validation Compute</div>
            <div class="station-glance-value">~13,400 core-hours</div>
            <div class="station-glance-detail">189 forest fits on 48-core high-memory HPC nodes.</div>
        </div>
    </div>

    <div class="testing-section">
        <h3>The Model</h3>
        <p>
            The model is a set of random forests, one per temperature variable. Each forest
            predicts the <strong>offset from a regional hub baseline</strong> instead of the
            temperature itself, and the baseline is added back afterward. That keeps the trees
            focused on local deviation rather than relearning the seasonal cycle.
        </p>
        <figure class="guide-figure">
            ${MODEL_FLOW_DIAGRAM_SVG}
            <figcaption>
                One daily estimate, end to end: readings from the 5 hubs and 10 neighbors join
                terrain and seasonality to form 873 features. The forest predicts only the local
                offset, which is added back to the regional hub baseline.
            </figcaption>
        </figure>
        <table class="spec-table">
            <tbody>
                <tr><td>Model family</td><td>Random forest regressor (scikit-learn), one model per variable (TAVG, TMIN, TMAX)</td></tr>
                <tr><td>Prediction design</td><td><code>regional_baseline + predicted_offset</code></td></tr>
                <tr><td>Features</td><td>873 inputs: 5 hub stations, 10 nearest neighbor stations, seasonality, station geometry, and DEM terrain (elevation, slope, aspect, relief)</td></tr>
                <tr><td>Production training set</td><td>2,174,509 daily rows across 761 target stations (TAVG)</td></tr>
                <tr><td>Production hyperparameters</td><td>300 trees, max depth 20, min 5 samples per leaf, fixed random seed</td></tr>
                <tr><td>Exported</td><td>2026-05-27 (serialized <code>model.joblib</code> with a model manifest and feature schema)</td></tr>
            </tbody>
        </table>
    </div>

    <div class="testing-section">
        <h3>How It Was Tested</h3>
        <p>
            <strong>Grouped station holdout.</strong> The 739 validation stations were split into
            189 groups of 2&ndash;5 stations. For each group, a separate forest was trained with every
            station in that group fully excluded, then asked to reconstruct those stations' real
            daily records. That adds up to 416,892 held-out station days. Because whole stations
            are held out rather than random days, each score shows how the model handles a
            station it has never seen before.
        </p>
        <figure class="guide-figure">
            ${HOLDOUT_SCHEMATIC_SVG}
            <figcaption>
                This cycle repeats 189 times, once per group, so every one of the 739 stations is
                scored by a forest that never saw it: 416,892 scored station days in total.
            </figcaption>
        </figure>
        <p>
            Two guardrails keep the metrics honest: baseline comparisons are <strong>row-locked</strong>
            (evaluated on the exact prediction rows, failing loudly if any baseline row is missing),
            and the exported predictions are independently re-scored by a separate C++ validator
            built on the app engine's own similarity code. The 2026-07-06 re-score reproduced the
            Python metrics at all 739 stations to within 0.003 F per station, so the headline
            numbers do not depend on a single implementation.
        </p>
        <table>
            <thead>
                <tr><th>Holdout Result (TAVG)</th><th>Value</th></tr>
            </thead>
            <tbody>
                <tr><td>Mean station MAE</td><td>2.68 F</td></tr>
                <tr><td>Median station MAE</td><td>2.49 F</td></tr>
                <tr><td>90th percentile station MAE</td><td>4.00 F</td></tr>
                <tr><td>Hardest station MAE</td><td>9.61 F</td></tr>
                <tr><td>Strict passes (MAE &le; 1.5 F, RMSE &le; 2.0 F, correlation &ge; 0.985)</td><td>52 / 739</td></tr>
            </tbody>
        </table>
        <p class="testing-note">
            The strict-pass bar is intentionally hard. 52 stations meet it today, and the count
            stays on the page so progress against it is visible.
        </p>
    </div>

    <div class="testing-section">
        <h3>Against Simple Baselines</h3>
        <p>
            Same 739 stations, same 416,892 held-out station days, zero missing baseline rows
            (row-locked comparison run 2026-06-11). Lower is better:
        </p>
        <div class="mae-bars" role="img" aria-label="Mean station MAE comparison: Paloma v1 2.68 F, inverse-distance weighting of 5 hubs 4.99 F, nearest hub 5.58 F">
            <div class="mae-bar-row">
                <span class="mae-bar-label">Paloma v1</span>
                <span class="mae-bar-track"><span class="mae-bar-fill model" style="width: 48%"></span></span>
                <span class="mae-bar-value">2.68 F</span>
            </div>
            <div class="mae-bar-row">
                <span class="mae-bar-label">IDW of 5 hubs</span>
                <span class="mae-bar-track"><span class="mae-bar-fill idw" style="width: 89%"></span></span>
                <span class="mae-bar-value">4.99 F</span>
            </div>
            <div class="mae-bar-row">
                <span class="mae-bar-label">Nearest hub</span>
                <span class="mae-bar-track"><span class="mae-bar-fill nearest" style="width: 100%"></span></span>
                <span class="mae-bar-value">5.58 F</span>
            </div>
        </div>
        <ul class="support-list">
            <li>Beats inverse-distance weighting at 588 of 739 stations (80%).</li>
            <li>Beats the nearest hub at 631 of 739 stations (85%).</li>
            <li>Strict passes: model 52, IDW 9, nearest hub 8.</li>
        </ul>
        <p>The full distributions tell the story better than the means:</p>
        <figure class="guide-figure">
            ${BASELINE_CDF_SVG}
            <figcaption>
                How to read it: for any error level on the x-axis, the curve height is the share of
                stations reconstructed at least that well. Higher and further left is better.
                Half the stations come in under 2.49 F with the model; on the exact same prediction
                rows, the IDW baseline does not reach its halfway point until about 4.2 F and the
                nearest hub until about 4.8 F.
            </figcaption>
        </figure>
    </div>

    <div class="testing-section">
        <h3>Where It Ran</h3>
        <p>
            All Paloma training and holdout validation ran on <strong>CU Boulder's Alpine
            supercomputer</strong> (CU Research Computing) as Slurm batch jobs on CPU partitions,
            with no GPUs involved. The project keeps a durable copy in <code>/projects</code> storage and runs
            jobs from <code>/scratch</code>; every job runs an environment and cache-integrity check
            before touching the model, and results sync back to durable storage before being
            retrieved into this repository. The app you are using now runs separately on
            Google Cloud Run.
        </p>
        <table>
            <thead>
                <tr><th>Job</th><th>Alpine Partition</th><th>Resources per Job</th></tr>
            </thead>
            <tbody>
                <tr><td>Grouped holdout training (Slurm job arrays)</td><td>amem (high-memory)</td><td>48 CPU cores &middot; 900 GB RAM &middot; 24 h wall limit</td></tr>
                <tr><td>Production model export</td><td>amem (high-memory)</td><td>48 CPU cores &middot; 900 GB RAM</td></tr>
                <tr><td>Training-table builds and merges</td><td>amilan (general CPU)</td><td>4&ndash;32 CPU cores</td></tr>
            </tbody>
        </table>
    </div>

    <div class="testing-section">
        <h3>How Long the Runs Took</h3>
        <div class="station-glance-grid">
            <div class="station-glance-card">
                <div class="station-glance-label">Holdout Forest Fits</div>
                <div class="station-glance-value">189</div>
                <div class="station-glance-detail">One fit per station group, run May&ndash;June 2026.</div>
            </div>
            <div class="station-glance-card">
                <div class="station-glance-label">Median Fit Time</div>
                <div class="station-glance-value">92 min</div>
                <div class="station-glance-detail">Mean 88 min on a 48-core allocation; ~1.65M training rows per fit.</div>
            </div>
            <div class="station-glance-card">
                <div class="station-glance-label">Fastest / Longest Fit</div>
                <div class="station-glance-value">25 min / 2 h 26 min</div>
                <div class="station-glance-detail">Measured wall time recorded by the training script for each fit.</div>
            </div>
            <div class="station-glance-card">
                <div class="station-glance-label">Total Node Time</div>
                <div class="station-glance-value">~278 hours</div>
                <div class="station-glance-detail">~13,400 core-hours, parallelized as Slurm job arrays.</div>
            </div>
        </div>
        <figure class="guide-figure">
            ${FIT_TIME_HISTOGRAM_SVG}
            <figcaption>
                All 189 measured fit times. Most cluster near the 92-minute median, with a smaller
                batch of fits completing in under 30 minutes.
            </figcaption>
        </figure>
        <p class="testing-note">
            Timings are the <code>elapsed_seconds</code> values the training script wrote into the
            holdout master artifact. They are measured wall time for each group fit, not
            scheduler estimates.
        </p>
    </div>

    <div class="testing-section">
        <h3>Sources</h3>
        <p class="testing-note">Every figure above traces to one of these project artifacts:</p>
        <ul class="support-list provenance-list">
            <li><code>alpine_outputs/paloma/paloma_v1_tavg_station_holdout_master.csv</code>: per-station holdout metrics and measured fit times</li>
            <li><code>model_runs/paloma_v1/paloma_v1_tavg/model_manifest.json</code>: production model card (rows, features, hyperparameters)</li>
            <li><code>weather_reconstruction_model/MODEL_RUNS.md</code>: verified claims and the row-locked baseline comparison</li>
            <li><code>docs/evidence/paloma_v1_tavg_holdout_cpp_validation.csv</code>: independent C++ re-score of all 739 holdout stations</li>
            <li><code>remote_jobs/*.sh</code>: Slurm job definitions (partitions, cores, memory, wall limits)</li>
        </ul>
    </div>
`;

export function renderModelTesting() {
    const section = document.getElementById("model-testing-section");
    if (!section) {
        return;
    }

    section.innerHTML = MODEL_TESTING_HTML;
}
