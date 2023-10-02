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

    this.getChildControl("captionbar").set({
      padding: 8
    });

    this.getChildControl("title").set({
      font: "text-14",
      rich: true
    });

    this._getLayout().setSeparator("separator-vertical");

    this.set({
      appearance: "service-window",
      backgroundColor: "background-main-2"
    });

    // Enable closing when clicking outside the modal
    this.addListener("appear", () => {
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

    const commandEsc = new qx.ui.command.Command("Esc");
    commandEsc.addListener("execute", () => this.close());
  },

  properties: {
    clickAwayClose: {
      check: "Boolean",
      init: false
    }
  },

  statics: {
    popUpInWindow: function(widget, title = "", width = 400, height = 400, icon) {
      const win = new osparc.ui.window.Window(title, icon).set({
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 10,
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        width: width,
        // height: height,
        modal: true,
        clickAwayClose: true
      });

      const scroll = new qx.ui.container.Scroll();
      scroll.add(widget);
      win.add(scroll);

      win.center();
      win.open();
      win.addListener("close", () => scroll.remove(widget));

      return win;
    }
  },

  members: {
    __recenter: null,

    // overridden
    center: function() {
      this.base(arguments);

      this.__recenter = true;
    },

    // overridden
    open: function() {
      if (this.__recenter) {
        // avoid flickering
        this.setOpacity(0);
        this.base(arguments);
        setTimeout(() => {
          this.center();
          this.setOpacity(1);
        }, 1);
      } else {
        this.base(arguments);
      }
    }
  }
});
