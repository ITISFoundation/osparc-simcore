/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.message.FlashMessageOEC", {
  extend: osparc.ui.message.FlashMessage,

  /**
   * Constructor for the FlashMessage.
   *
   * @param {String} message Message that the user will read.
   * @param {Number} duration
   * @param {String} supportId
   */
  construct: function(message, duration, supportId) {
    this.base(arguments, message, "ERROR", duration*2);

    if (osparc.product.Utils.isSupportEnabled()) {
      console.log("bring it to support chat");
    } else {
      const oecAtom = this.getChildControl("oec-atom");
      this.bind("supportId", oecAtom, "label");
      this.setSupportId(supportId);
    }
  },

  properties: {
    supportId: {
      check: "String",
      nullable: true,
      event: "changeSupportId",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "oec-atom":
          control = new qx.ui.basic.Atom().set({
            icon: "@FontAwesome5Solid/copy/10",
            iconPosition: "right",
            gap: 8,
            cursor: "pointer",
            alignX: "center",
            allowGrowX: false,
          });
          control.addListener("tap", () => {
            const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
            const dataToClipboard = {
              message: this.getMessage(),
              supportId: this.getSupportId(),
              timestamp: new Date().toString(),
              url: window.location.href,
              releaseTag: osparc.utils.Utils.getReleaseTag(),
              studyId: currentStudy ? currentStudy.getUuid() : "",
            }
            osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(dataToClipboard));
          });
          this.addWidget(control);
          break;
      }
      return control || this.base(arguments, id);
    },
  }
});
