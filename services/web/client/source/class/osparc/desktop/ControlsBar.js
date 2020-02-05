/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows the play/stop study button.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let controlsBar = new osparc.desktop.ControlsBar();
 *   this.getRoot().add(controlsBar);
 * </pre>
 */

qx.Class.define("osparc.desktop.ControlsBar", {
  extend: qx.ui.toolbar.ToolBar,

  construct: function() {
    this.base(arguments);

    this.setSpacing(10);
    this.setAppearance("sidepanel");

    this.__initDefault();
  },

  events: {
    "showWorkbench": "qx.event.type.Event",
    "showSettings": "qx.event.type.Event",
    "groupSelection": "qx.event.type.Event",
    "ungroupSelection": "qx.event.type.Event",
    "startPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __startButton: null,
    __stopButton: null,
    __groupButton: null,
    __ungroupButton: null,
    __workbenchViewButton: null,
    __settingsViewButton: null,

    setWorkbenchVisibility: function(isWorkbenchContext) {
      this.__serviceFilters.setVisibility(isWorkbenchContext ? "visible" : "excluded");
      this.__groupButton.setVisibility(isWorkbenchContext ? "visible" : "excluded");
      this.__ungroupButton.setVisibility(isWorkbenchContext ? "visible" : "excluded");
    },

    setExtraViewVisibility: function(hasExtraView) {
      this.__workbenchViewButton.setVisibility(hasExtraView ? "visible" : "excluded");
      this.__settingsViewButton.setVisibility(hasExtraView ? "visible" : "excluded");
    },

    __initDefault: function() {
      const filterCtrls = new qx.ui.toolbar.Part();
      const serviceFilters = this.__serviceFilters = new osparc.component.filter.group.ServiceFilterGroup("workbench");
      osparc.component.filter.UIFilterController.getInstance().registerContainer("workbench", serviceFilters);
      filterCtrls.add(serviceFilters);
      this.add(filterCtrls);

      this.addSpacer();

      const viewCtrls = new qx.ui.toolbar.Part();
      const workbenchViewButton = this.__workbenchViewButton = this.__createWorkbenchButton();
      const settingsViewButton = this.__settingsViewButton = this.__createSettingsButton();
      viewCtrls.add(workbenchViewButton);
      viewCtrls.add(settingsViewButton);
      this.add(viewCtrls);
      const viewRadioGroup = new qx.ui.form.RadioGroup();
      viewRadioGroup.add(workbenchViewButton, settingsViewButton);

      const groupCtrls = new qx.ui.toolbar.Part();
      const groupButton = this.__groupButton = this.__createGroupButton();
      const ungroupButton = this.__ungroupButton = this.__createUngroupButton();
      groupCtrls.add(groupButton);
      groupCtrls.add(ungroupButton);
      this.add(groupCtrls);

      const simCtrls = new qx.ui.toolbar.Part();
      const startButton = this.__startButton = this.__createStartButton();
      const stopButton = this.__stopButton = this.__createStopButton();
      simCtrls.add(startButton);
      simCtrls.add(stopButton);
      this.add(simCtrls);
    },

    __createWorkbenchButton: function() {
      const workbenchButton = this.__createRadioButton(this.tr("Workbench view"), "vector-square", "workbenchViewBtn", "showWorkbench");
      return workbenchButton;
    },

    __createSettingsButton: function() {
      const settingsButton = this.__createRadioButton(this.tr("Node view"), "list", "settingsViewBtn", "showSettings");
      return settingsButton;
    },

    __createGroupButton: function() {
      const groupButton = this.__createButton(this.tr("Group Nodes"), "object-group", "groupNodesBtn", "groupSelection");
      return groupButton;
    },

    __createUngroupButton: function() {
      const ungroupButton = this.__createButton(this.tr("Ungroup Nodes"), "object-ungroup", "ungroupNodesBtn", "ungroupSelection");
      return ungroupButton;
    },

    __createStartButton: function() {
      const startButton = this.__createButton(this.tr("Run"), "play", "runStudyBtn", "startPipeline");
      return startButton;
    },

    __createStopButton: function() {
      const stopButton = this.__createButton(this.tr("Stop"), "stop-circle", "stopStudyBtn", "stopPipeline");
      return stopButton;
    },

    __createRadioButton: function(label, icon, widgetId, singalName) {
      const button = new qx.ui.toolbar.RadioButton(label);
      // button.setIcon("@FontAwesome5Solid/"+icon+"/14");
      osparc.utils.Utils.setIdToWidget(button, widgetId);
      button.addListener("execute", () => {
        this.fireEvent(singalName);
      }, this);
      return button;
    },

    __createButton: function(label, icon, widgetId, singalName) {
      const button = new qx.ui.toolbar.Button(label, "@FontAwesome5Solid/"+icon+"/14");
      osparc.utils.Utils.setIdToWidget(button, widgetId);
      button.addListener("execute", () => {
        this.fireEvent(singalName);
      }, this);
      return button;
    }
  }
});
