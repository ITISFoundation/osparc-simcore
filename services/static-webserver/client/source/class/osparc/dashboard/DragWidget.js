/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.DragWidget", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle",
    }));

    this.set({
      opacity: 0.9,
      padding: 10,
      zIndex: 1000,
      backgroundColor: "strong-main",
      decorator: "rounded",
      visibility: "excluded",
    });

    const root = qx.core.Init.getApplication().getRoot();
    root.add(this);

    this.initDropAllowed();
  },

  properties: {
    dropAllowed: {
      check: "Boolean",
      nullable: false,
      init: null,
      apply: "__dropAllowed",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "allowed-icon":
          control = new qx.ui.basic.Image();
          this._add(control);
          break;
        case "dragged-resource":
          control = new qx.ui.basic.Atom().set({
            font: "text-14",
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __dropAllowed: function(allowed) {
      this.getChildControl("allowed-icon").set({
        source: allowed ? "@FontAwesome5Solid/check/14" : "@FontAwesome5Solid/times/14",
        textColor: allowed ? "text" : "danger-red",
      });
    },

    __onMouseMoveDragging: function(e) {
      if (this.getContentElement()) {
        // place it next to the "dragdrop-own-cursor" indicator
        const domEl = this.getContentElement().getDomElement();
        domEl.style.left = `${e.pageX + 15}px`;
        domEl.style.top = `${e.pageY + 5}px`;
      }
    },

    start: function() {
      this.show();
      document.addEventListener("mousemove", this.__onMouseMoveDragging.bind(this), false);

      const cursor = qx.ui.core.DragDropCursor.getInstance();
      cursor.setAppearance("dragdrop-no-cursor");
    },

    end: function() {
      this.exclude();
      document.removeEventListener("mousemove", this.__onMouseMoveDragging.bind(this), false);

      const cursor = qx.ui.core.DragDropCursor.getInstance();
      cursor.setAppearance("dragdrop-cursor");
    },
  }
});
