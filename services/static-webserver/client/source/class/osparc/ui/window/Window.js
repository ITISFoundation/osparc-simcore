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
      padding: 8,
      cursor: "move",
    });

    this.getChildControl("title").set({
      font: "text-14",
      rich: true,
      cursor: "move",
    });

    this._getLayout().setSeparator("separator-vertical");

    this.set({
      appearance: "service-window",
      backgroundColor: "window-popup-background"
    });

    this.addListener("appear", () => this.__afterAppear(), this);
    this.addListener("move", () => this.__windowMoved(), this);
    // make the window smaller if it doesn't fit the screen
    window.addEventListener("resize", this.__keepWithinScreen);

    const commandEsc = new qx.ui.command.Command("Esc");
    commandEsc.addListener("execute", () => {
      this.fireEvent("cancel");
      this.close();
    });
  },

  properties: {
    clickAwayClose: {
      check: "Boolean",
      init: false
    },

    // it will be used to center the window within that element
    centerOnElement: {
      init: null,
      nullable: true,
    },
  },

  events: {
    "cancel": "qx.event.type.Event"
  },

  statics: {
    popUpInWindow: function(widget, title = "", width = 400, minHeight = 400, icon) {
      const win = new osparc.ui.window.Window(title, icon).set({
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 10,
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        width,
        minHeight,
        maxHeight: Math.max(minHeight, document.documentElement.clientHeight),
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

      if (this.getCenterOnElement()) {
        this.__centerWithinElement(this.getCenterOnElement());
      }

      this.__recenter = true;
    },

    // overridden
    open: function() {
      if (this.__recenter) {
        // avoid flickering
        this.setOpacity(0);
        this.base(arguments);
        setTimeout(() => {
          if (this) {
            this.center();
            if (this.getContentElement()) {
              this.setOpacity(1);
            }
          }
        }, 1);
        // keep it centered
        window.addEventListener("resize", () => this.center());
      } else {
        this.base(arguments);
      }
    },

    moveItUp: function(up=100) {
      setTimeout(() => {
        const props = this.getLayoutProperties();
        this.moveTo(props.left, Math.max(props.top-up, 0));
      }, 2);
    },

    __afterAppear: function() {
      // Enable closing when clicking outside the modal
      const thisDom = this.getContentElement().getDomElement();
      const thisZIndex = parseInt(thisDom.style.zIndex);
      const modalFrame = qx.dom.Hierarchy.getSiblings(thisDom).find(el =>
        // Hack: Qx inserts the modalFrame as a sibling of the window with a -1 zIndex
        parseInt(el.style.zIndex) === thisZIndex - 1
      );
      if (modalFrame) {
        modalFrame.addEventListener("click", () => {
          if (
            this.isClickAwayClose() &&
            parseInt(modalFrame.style.zIndex) === parseInt(thisDom.style.zIndex) - 1
          ) {
            this.close();
          }
        });
        modalFrame.style.backgroundColor = "black";
        modalFrame.style.opacity = 0.4;
      }

      this.__keepWithinScreen();
    },

    __centerWithinElement: function(element) {
      if (!element || !element.getContentElement()) {
        return;
      }

      const domElement = element.getContentElement().getDomElement();
      const elemRect = domElement.getBoundingClientRect();
      const winSizeHint = this.getSizeHint();
      const left = parseInt(elemRect.left + (elemRect.width - winSizeHint.width) / 2);
      const top = parseInt(elemRect.top + (elemRect.height - winSizeHint.height) / 2);
      this.moveTo(left, top);
    },

    __windowMoved: function() {
      // enforce it stays within the screen
      const bounds = this.getBounds() || this.getSizeHint(); // current window position/size
      const root = qx.core.Init.getApplication().getRoot();
      const rootBounds = root.getBounds(); // available screen area
      if (!bounds || !rootBounds) {
        return;
      }

      let {
        left,
        top,
      } = bounds;

      // Clamp horizontal position
      left = Math.min(
        Math.max(left, 0),
        rootBounds.width - bounds.width
      );

      // Clamp vertical position
      top = Math.min(
        Math.max(top, 0),
        rootBounds.height - bounds.height
      );

      // Only apply correction if needed
      if (left !== bounds.left || top !== bounds.top) {
        this.moveTo(left, top);
      }
    },

    __keepWithinScreen: function() {
      // ensure it fits within the screen
      const bounds = this.getBounds() || this.getSizeHint(); // current window position/size
      const root = qx.core.Init.getApplication().getRoot();
      const rootBounds = root.getBounds(); // available screen area
      if (!bounds || !rootBounds) {
        return;
      }

      let {
        width,
        height,
        left,
        top
      } = bounds;

      let resized = false;

      // Adjust width if needed
      if (width > rootBounds.width) {
        width = rootBounds.width;
        resized = true;
      }

      // Adjust height if needed
      if (height > rootBounds.height) {
        height = rootBounds.height;
        resized = true;
      }

      // Clamp horizontal position
      left = Math.min(
        Math.max(left, 0),
        rootBounds.width - width
      );

      // Clamp vertical position
      top = Math.min(
        Math.max(top, 0),
        rootBounds.height - height
      );

      // Apply changes if any
      if (resized) {
        if (width < this.getMinWidth()) {
          this.setMinWidth(width);
        }
        if (height < this.getMinHeight()) {
          this.setMinHeight(height);
        }
        this.set({
          width,
          height
        });
        this.moveTo(left, top);
      }
    },
  },

  destruct: function() {
    window.removeEventListener("resize", this.__keepWithinScreen);
  },
});
