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
    this.__attachEventHandlers();
  },

  events: {
    "showWorkbench": "qx.event.type.Event",
    "showSettings": "qx.event.type.Event",
    "groupSelection": "qx.event.type.Event",
    "ungroupSelection": "qx.event.type.Event"
  },

  members: {
    __serviceFilters: null,
    __viewCtrls: null,
    __workbenchViewButton: null,
    __settingsViewButton: null,
    __iterationCtrls: null,
    __parametersButton: null,

    setWorkbenchVisibility: function(isWorkbenchContext) {
      this.__serviceFilters.setVisibility(isWorkbenchContext ? "visible" : "excluded");
    },

    setExtraViewVisibility: function(hasExtraView) {
      this.__viewCtrls.setVisibility(hasExtraView ? "visible" : "excluded");
    },

    __initDefault: function() {
      const filterCtrls = new qx.ui.toolbar.Part();
      const serviceFilters = this.__serviceFilters = new osparc.filter.group.ServiceFilterGroup("workbench");
      osparc.filter.UIFilterController.getInstance().registerContainer("workbench", serviceFilters);
      filterCtrls.add(serviceFilters);
      this.add(filterCtrls);

      this.addSpacer();

      const viewCtrls = this.__viewCtrls = new qx.ui.toolbar.Part();
      const workbenchViewButton = this.__workbenchViewButton = this.__createWorkbenchButton();
      const settingsViewButton = this.__settingsViewButton = this.__createSettingsButton();
      viewCtrls.add(workbenchViewButton);
      viewCtrls.add(settingsViewButton);
      this.add(viewCtrls);
      const viewRadioGroup = new qx.ui.form.RadioGroup();
      viewRadioGroup.add(workbenchViewButton, settingsViewButton);
    },

    __createWorkbenchButton: function() {
      const workbenchButton = this.__createRadioButton(this.tr("Workbench view"), "vector-square", "workbenchViewBtn", "showWorkbench");
      return workbenchButton;
    },

    __createSettingsButton: function() {
      const settingsButton = this.__createRadioButton(this.tr("Node view"), "list", "settingsViewBtn", "showSettings");
      return settingsButton;
    },

    __createRadioButton: function(label, icon, widgetId, singalName) {
      const button = new qx.ui.toolbar.RadioButton(label);
      // button.setIcon("@FontAwesome5Solid/"+icon+"/14");
      osparc.utils.Utils.setIdToWidget(button, widgetId);
      button.addListener("execute", () => {
        this.fireEvent(singalName);
      }, this);
      return button;
    }
  }
});
