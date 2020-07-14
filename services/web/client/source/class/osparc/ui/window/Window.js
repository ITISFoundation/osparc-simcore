/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.window.Window", {
  extend: qx.ui.window.Window,
  construct: function(caption, icon) {
    this.base(arguments, caption, icon);
    this.set({
      appearance: "service-window",
      backgroundColor: "material-button-background"
    });
    this.addListener("appear", () => {
      // Enable closing when clicking outside the modal
      const thisDom = this.getContentElement().getDomElement();
      const thisZIndex = parseInt(thisDom.style.zIndex);
      const modalFrame = qx.dom.Hierarchy.getSiblings(thisDom).find(el =>
        // Hack: Qx inserts the modalFrame as a sibling of the window with a -1 zIndex
        parseInt(el.style.zIndex) === thisZIndex - 1
      );
      if (modalFrame) {
        modalFrame.addEventListener("click", () => {
          if (this.isModal() && this.isClickAwayClose() &&
            parseInt(modalFrame.style.zIndex) === parseInt(thisDom.style.zIndex) - 1) {
            this.close();
          }
        });
        modalFrame.style.backgroundColor = "black";
        modalFrame.style.opacity = 0.4;
      }
    });
  },
  properties: {
    clickAwayClose: {
      check: "Boolean",
      init: false
    }
  }
});
