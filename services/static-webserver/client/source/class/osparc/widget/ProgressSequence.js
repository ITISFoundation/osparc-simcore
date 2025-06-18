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

  construct: function(title) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(9));

    this.set({
      backgroundColor: "window-popup-background",
      paddingBottom: 8,
      minWidth: 400,
      maxWidth: 400,
    });

    this.__initLayout(title);

    this.__tasks = [];
  },

  statics: {
    POS: {
      LABEL: 0,
      CALC: 1,
      HALO: 2,
    },

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
      layout.addAt(lbl, this.POS.LABEL, {
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
      layout.addAt(iconContainer, this.POS.HALO);

      const progressState = new qx.ui.basic.Label();
      progressState.set({
        value: qx.locale.Manager.tr("Waiting ..."),
        textColor: "text",
        allowGrowX: true,
        allowShrinkX: true
      });
      layout.addAt(progressState, this.POS.CALC);

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
    },

    updateTaskProgress: function(atom, {value, progressLabel}) {
      if ([null, undefined].includes(value)) {
        return;
      }

      if (atom) {
        const halo = atom.getChildren()[this.POS.HALO];
        const icon = halo.getChildren()[0];
        icon.setVisibility(value === 1 ? "visible" : "excluded");
        const progressColor = qx.theme.manager.Color.getInstance().resolve("progressbar")
        osparc.service.StatusUI.getStatusHalo(halo, progressColor, value * 100);

        const label = atom.getChildren()[this.POS.CALC];
        label.setValue(progressLabel);
      }
    },

    progressUpdate: function(pBar, value) {
      if ([null, undefined].includes(value)) {
        return;
      }

      if (pBar) {
        pBar.set({
          value,
          visibility: (value >= 0) ? "visible" : "excluded"
        });
      }
    }
  },

  properties: {
    overallProgress: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyOverallProgress"
    }
  },

  members: {
    __tasks: null,

    __initLayout: function(title) {
      title = title || qx.locale.Manager.tr("CREATING ...");
      const progressTitle = new qx.ui.basic.Label(title).set({
        font: "text-12",
        alignX: "center",
        alignY: "middle",
        margin: 10
      });
      this._add(progressTitle);
    },

    __applyOverallProgress: function(value) {
      this.self().progressUpdate(this.__overallProgressBar, value);
    },

    getTask: function(text) {
      const taskFound = this.__tasks.find(task => {
        if (task.getChildren().length > this.self().POS.LABEL) {
          return task.getChildren()[this.self().POS.LABEL].getValue() === text;
        }
        return false;
      });
      return taskFound;
    },

    getTasks: function() {
      return this.__tasks;
    },

    addOverallProgressBar: function(nTasks = 1) {
      const overallPBar = this.__overallProgressBar = osparc.widget.ProgressSequence.createProgressBar(nTasks);
      this._add(overallPBar);
      return overallPBar;
    },

    addNewTask: function(text) {
      const taskFound = this.getTask(text);
      if (taskFound) {
        return taskFound;
      }
      const newTask = osparc.widget.ProgressSequence.createTaskLayout(text);
      this._add(newTask);
      this.__tasks.push(newTask);
      return newTask;
    }
  }
});
