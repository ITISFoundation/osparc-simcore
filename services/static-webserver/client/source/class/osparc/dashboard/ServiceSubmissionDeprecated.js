/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(form/service.json)
 * @asset(form/service-data.json)
 * @ignore(Headers)
 * @ignore(fetch)
 * @deprecated Service submission is deprecated and will be removed in a future release.
 */
qx.Class.define("osparc.dashboard.ServiceSubmissionDeprecated", {
  extend: qx.core.Object,

  construct: function(toolbar) {
    this.base(arguments);

    this.__toolbar = toolbar;
    this.__addButtons();
  },

  members: {
    __toolbar: null,

    __addButtons: function() {
      const platformName = osparc.store.StaticInfo.getPlatformName();
      const hasRights = osparc.data.Permissions.getInstance().canDo("studies.template.create.productAll");
      if (platformName === "dev") {
        const testDataButton = new qx.ui.form.Button(qx.locale.Manager.tr("Test with data"), "@FontAwesome5Solid/plus-circle/14");
        testDataButton.addListener("execute", () => {
          osparc.utils.Utils.fetchJSON("/resource/form/service-data.json")
            .then(data => {
              this.__displayServiceSubmissionForm(data);
            });
        });
        this.__toolbar.add(testDataButton);
      }

      const addServiceButton = new qx.ui.form.Button(qx.locale.Manager.tr("Submit new app"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.set({
        appearance: "form-button-outlined",
        visibility: hasRights ? "visible" : "excluded"
      });
      addServiceButton.addListener("execute", () => this.__displayServiceSubmissionForm());
      this.__toolbar.add(addServiceButton);
    },

    __displayServiceSubmissionForm: function(formData) {
      const addServiceWindow = new osparc.ui.window.Window(qx.locale.Manager.tr("Submit a new app")).set({
        modal: true,
        autoDestroy: true,
        showMinimize: false,
        allowMinimize: false,
        centerOnAppear: true,
        layout: new qx.ui.layout.Grow(),
        width: 600,
        height: 660
      });
      const scroll = new qx.ui.container.Scroll();
      addServiceWindow.add(scroll);

      const deprecatedMsg = qx.locale.Manager.tr("Service submission is deprecated and will be removed in a future release.");
      osparc.FlashMessenger.logAs(deprecatedMsg, "WARNING");

      const form = new osparc.form.json.JsonSchemaForm("/resource/form/service.json", formData);
      form.addListener("ready", () => {
        addServiceWindow.open();
      });
      form.addListener("submit", e => {
        const data = e.getData();
        const headers = new Headers();
        headers.append("Accept", "application/json");
        const body = new FormData();
        body.append("metadata", new Blob([JSON.stringify(data.json)], {
          type: "application/json"
        }));
        if (data.files && data.files.length) {
          const size = data.files[0].size;
          const maxSize = 10 * 1000 * 1000; // 10 MB
          if (size > maxSize) {
            osparc.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          body.append("attachment", data.files[0], data.files[0].name);
        }
        form.setFetching(true);
        const deprecatedEndpoint = "/v0/publications/service-submission"; // Deprecated endpoint.
        fetch(deprecatedEndpoint, {
          method: "POST",
          headers,
          body
        })
          .then(resp => {
            if (resp.ok) {
              osparc.FlashMessenger.logAs("Your data was sent to our curation team. We will get back to you shortly.", "INFO");
              addServiceWindow.close();
            } else {
              osparc.FlashMessenger.logAs(`A problem occurred while processing your data: ${resp.statusText}`, "ERROR");
            }
          })
          .finally(() => form.setFetching(false));
      });
      scroll.add(form);
    }
  }
});
