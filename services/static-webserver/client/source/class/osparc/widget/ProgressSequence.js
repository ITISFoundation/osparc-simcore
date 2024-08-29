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

qx.Class.define("osparc.widget.ProgressSequence", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    // Layout
    this._setLayout(new qx.ui.layout.VBox());
  },

  statics: {
    createTaskLayout: function(label) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      })).set({
        padding: [2, 10]
      });

      const lbl = new qx.ui.basic.Label(label);
      lbl.set({
        textColor: "text",
        allowGrowX: true,
        allowShrinkX: true,
      });
      layout.addAt(lbl, this.NODE_INDEX.LABEL, {
        flex: 1
      });

      const iconContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignY: "middle",
        alignX: "center",
      })).set({
        height: 18,
        width: 18,
        allowGrowY: false,
        allowGrowX: false,
      });
      const icon = new qx.ui.basic.Image("@FontAwesome5Solid/check/10").set({
        visibility: "excluded",
        textColor: "success"
      });
      iconContainer.add(icon);
      const progressColor = qx.theme.manager.Color.getInstance().resolve("progressbar");
      osparc.service.StatusUI.getStatusHalo(iconContainer, progressColor, 0);
      layout.addAt(iconContainer, this.NODE_INDEX.HALO);

      const progressState = new qx.ui.basic.Label();
      progressState.set({
        value: qx.locale.Manager.tr("Waiting ..."),
        textColor: "text",
        allowGrowX: true,
        allowShrinkX: true
      });
      layout.addAt(progressState, this.NODE_INDEX.CALC);

      return layout;
    },

    createProgressBar: function(max = 1) {
      const progressBar = new qx.ui.indicator.ProgressBar().set({
        maximum: max,
        height: 4,
        margin: 0,
        padding: 0
      });
      progressBar.exclude();
      return progressBar;
    }
  },

  properties: {
  },

  members: {

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});
