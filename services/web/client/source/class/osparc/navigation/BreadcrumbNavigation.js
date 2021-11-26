/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.navigation.BreadcrumbNavigation", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(0).set({
      alignY: "middle"
    }));
  },

  events: {
    "nodeSelected": "qx.event.type.Data"
  },

  members: {
    /**
      * @abstract
      */
    populateButtons: function(nodesIds = []) {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      */
    _createBtns: function(nodeId) {
      throw new Error("Abstract method called!");
    },

    _createNodeBtn: function(nodeId) {
      const btn = new qx.ui.form.ToggleButton().set({
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        maxWidth: 200
      });
      btn.addListener("execute", () => {
        this.fireDataEvent("nodeSelected", nodeId);
      }, this);
      return btn;
    },

    _buttonsToBreadcrumb: function(btns, shape = "slash") {
      this._removeAll();
      for (let i=0; i<btns.length; i++) {
        const thisBtn = btns[i];
        let nextBtn = null;
        if (i+1<btns.length) {
          nextBtn = btns[i+1];
        }

        this._add(thisBtn);

        const breadcrumbSplitter = new osparc.navigation.BreadcrumbSplitter(16, 32).set({
          shape,
          marginLeft: -1,
          marginRight: -1
        });
        const addLeftRightWidgets = (leftBtn, rightBtn) => {
          if (shape === "separator" && (!leftBtn || !rightBtn)) {
            return;
          }
          breadcrumbSplitter.setLeftWidget(leftBtn);
          if (rightBtn) {
            breadcrumbSplitter.setRightWidget(rightBtn);
          }
        };
        if (breadcrumbSplitter.getReady()) {
          addLeftRightWidgets(thisBtn, nextBtn);
        } else {
          breadcrumbSplitter.addListenerOnce("SvgWidgetReady", () => {
            addLeftRightWidgets(thisBtn, nextBtn);
          }, this);
        }
        this._add(breadcrumbSplitter);
      }
    }
  }
});
