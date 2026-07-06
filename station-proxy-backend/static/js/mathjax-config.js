// Purpose: Configure MathJax before the external renderer script loads.

window.MathJax = {
    tex: {
        inlineMath: [["\\(", "\\)"]],
        displayMath: [["\\[", "\\]"]]
    },
    svg: {
        fontCache: "global"
    }
};
