/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.dashboard.resources.pages.BasePage", {
  extend: qx.ui.tabview.Page,

  construct: function(title, iconSrc = null, id) {
    this.base(arguments, null, iconSrc, id);

    const grid = new qx.ui.layout.Grid(10, 10);
    grid.setColumnFlex(0, 1);
    grid.setRowFlex(0, 0); // header
    grid.setRowFlex(1, 1); // content
    grid.setRowFlex(2, 0); // footer
    grid.setRowAlign(0, "right", "top"); // header
    grid.setRowAlign(0, "left", "top"); // content
    grid.setRowAlign(0, "right", "top"); // footer

    this.setLayout(grid);

    this.__showLabelOnTab(title);

    this.set({
      backgroundColor: "window-popup-background",
      paddingTop: 0,
      paddingLeft: 15
    });
  },

  statics: {
    decorateHeaderButton: function(btn) {
      btn.set({
        appearance: "form-button",
        font: "text-14",
        alignX: "right",
        minWidth: 150,
        maxWidth: 150,
        height: 35,
        center: true
      });
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title": {
          control = new qx.ui.basic.Label().set({
            font: "title-14",
            alignX: "left"
          });
          this.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __showLabelOnTab: function(tabTitle) {
      this.getChildControl("title").set({
        visibility: "excluded"
      });

      const tabButton = this.getChildControl("button");
      tabButton.set({
        label: tabTitle,
        font: "text-14"
      });
      // eslint-disable-next-line no-underscore-dangle
      const buttonLayout = tabButton._getLayout();
      buttonLayout.setColumnAlign(0, "center", "middle"); // center icon
      buttonLayout.setColumnWidth(0, 24); // align texts
      buttonLayout.setSpacingX(5);
    },

    addToHeader: function(widget) {
      this.add(widget, {
        column: 0,
        row: 0
      });
    },

    addToContent: function(widget) {
      const scrollContainer = new qx.ui.container.Scroll(widget);
      this.add(scrollContainer, {
        column: 0,
        row: 1
      });
    },

    addToFooter: function(widget) {
      this.add(widget, {
        column: 0,
        row: 2
      });
    }
  }
});
