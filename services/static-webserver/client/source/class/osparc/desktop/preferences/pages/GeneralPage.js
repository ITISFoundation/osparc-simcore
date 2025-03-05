/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.desktop.preferences.pages.GeneralPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
      this.__addCreditsIndicatorSettings();
    }

    const preferences = osparc.Preferences.getInstance();
    if (preferences.getLowDiskSpaceThreshold()) {
      this.__addLowDiskSpaceSetting();
    }

    if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
      this.__addInactivitySetting();
    }

    // this.__addJobConcurrencySetting();

    if (osparc.product.Utils.isS4LProduct() || osparc.product.Utils.isProduct("s4llite")) {
      this.__addS4LUserPrivacySettings();
    }
  },

  members: {
    __addCreditsIndicatorSettings: function() {
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Credits Indicator"));

      const form = new qx.ui.form.Form();

      const preferencesSettings = osparc.Preferences.getInstance();

      const walletIndicatorVisibilitySB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      [{
        id: "always",
        label: "Always"
      }, {
        id: "warning",
        label: "Warning"
      }].forEach(options => {
        const lItem = new qx.ui.form.ListItem(options.label, null, options.id);
        walletIndicatorVisibilitySB.add(lItem);
      });
      const value = preferencesSettings.getWalletIndicatorVisibility();
      walletIndicatorVisibilitySB.getSelectables().forEach(selectable => {
        if (selectable.getModel() === value) {
          walletIndicatorVisibilitySB.setSelection([selectable]);
        }
      });
      walletIndicatorVisibilitySB.addListener("changeValue", e => {
        const selectable = e.getData();
        osparc.Preferences.patchPreferenceField("walletIndicatorVisibility", walletIndicatorVisibilitySB, selectable.getModel());
      });
      form.add(walletIndicatorVisibilitySB, this.tr("Show indicator"));

      const creditsWarningThresholdField = new qx.ui.form.Spinner().set({
        minimum: 50,
        maximum: 10000,
        singleStep: 10,
        allowGrowX: false
      });
      preferencesSettings.bind("creditsWarningThreshold", creditsWarningThresholdField, "value");
      creditsWarningThresholdField.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("creditsWarningThreshold", creditsWarningThresholdField, e.getData()));
      form.add(creditsWarningThresholdField, this.tr("Show warning when credits below"));

      box.add(new qx.ui.form.renderer.Single(form));

      this._add(box);
    },

    __addInactivitySetting: function() {
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Automatic Shutdown of Idle Instances"));

      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr("Enter 0 to disable this function"), "text-13-italic");
      box.add(label);

      const form = new qx.ui.form.Form();
      const inactivitySpinner = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: Number.MAX_SAFE_INTEGER,
        singleStep: 1,
        allowGrowX: false
      });
      const preferences = osparc.Preferences.getInstance();
      preferences.bind("userInactivityThreshold", inactivitySpinner, "value", {
        converter: value => Math.round(value / 60) // Stored in seconds, displayed in minutes
      });
      inactivitySpinner.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("userInactivityThreshold", inactivitySpinner, e.getData() * 60));
      form.add(inactivitySpinner, this.tr("Idle time before closing (in minutes)"));

      box.add(new qx.ui.form.renderer.Single(form));

      this._add(box);
    },

    __addJobConcurrencySetting: function() {
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Job Concurrency"));
      const form = new qx.ui.form.Form();
      const jobConcurrencySpinner = new qx.ui.form.Spinner().set({
        minimum: 1,
        maximum: 10,
        singleStep: 1,
        allowGrowX: false,
        enabled: false
      });
      const preferences = osparc.Preferences.getInstance();
      preferences.bind("jobConcurrencyLimit", jobConcurrencySpinner, "value");
      jobConcurrencySpinner.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("jobConcurrencyLimit", jobConcurrencySpinner, e.getData()));
      form.add(jobConcurrencySpinner, this.tr("Maximum number of concurrent jobs"));
      box.add(new qx.ui.form.renderer.Single(form));
      this._add(box);
    },

    __addLowDiskSpaceSetting: function() {
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Low Disk Space Threshold"));
      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr("Set the warning Threshold for Low Disk Space availability"), "text-13-italic");
      box.add(label);
      const form = new qx.ui.form.Form();
      const diskUsageSpinner = new qx.ui.form.Spinner().set({
        minimum: 1,
        maximum: 10000,
        singleStep: 1,
        allowGrowX: false,
        enabled: true
      });
      const preferences = osparc.Preferences.getInstance();
      preferences.bind("lowDiskSpaceThreshold", diskUsageSpinner, "value");

      diskUsageSpinner.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("lowDiskSpaceThreshold", diskUsageSpinner, e.getData()));
      form.add(diskUsageSpinner, this.tr("Threshold (in GB)"));
      box.add(new qx.ui.form.renderer.Single(form));
      this._add(box);
    },

    __addS4LUserPrivacySettings: function() {
      const box = osparc.ui.window.TabbedView.createSectionBox("Privacy Settings");

      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr("Help us improve Sim4Life user experience"), "text-13-italic");
      box.add(label);

      const preferencesSettings = osparc.Preferences.getInstance();

      const cbAllowMetricsCollection = new qx.ui.form.CheckBox(this.tr("Share usage data"));
      preferencesSettings.bind("allowMetricsCollection", cbAllowMetricsCollection, "value");
      cbAllowMetricsCollection.addListener("changeValue", e => osparc.Preferences.patchPreferenceField("allowMetricsCollection", cbAllowMetricsCollection, e.getData()));
      box.add(cbAllowMetricsCollection);

      this._add(box);
    }
  }
});
