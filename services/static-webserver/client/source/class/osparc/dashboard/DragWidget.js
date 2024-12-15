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
  extend: qx.ui.basic.Atom,

  construct: function() {
    this.base(arguments);

    this.set({
      opacity: 0.9,
      padding: 10,
      zIndex: 1000,
      font: "text-14",
      backgroundColor: "strong-main",
      decorator: "rounded",
      visibility: "excluded",
    });

    const root = qx.core.Init.getApplication().getRoot();
    root.add(this);
  },

  members: {
    __onMouseMoveDragging: function(e) {
      const domEl = this.getContentElement().getDomElement();
      domEl.style.left = `${e.pageX + 15}px`; // Offset for better visibility
      domEl.style.top = `${e.pageY + 15}px`;
    },

    start: function() {
      this.show();
      document.addEventListener("mousemove", this.__onMouseMoveDragging.bind(this), false);
    },

    end: function() {
      this.exclude();
      document.removeEventListener("mousemove", this.__onMouseMoveDragging.bind(this), false);
    },
  }
});
