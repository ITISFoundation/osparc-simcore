/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.VendorInfo", {
  extend: qx.core.Object,
  type: "singleton",

  members: {
    __getFromStaticInfo: function(key, defaultValue) {
      const staticValue = osparc.store.StaticInfo.getInstance().getValue(key);
      if (staticValue) {
        return staticValue;
      }
      return defaultValue;
    },

    getSupportEmail: function() {
      return this.__getFromStaticInfo("supportEmail", "support@osparc.io");
    },

    getVendor: function() {
      /*
      {
        "name": "ACME",
        "copyright": "\u00a9 ACME correcaminos",
        "url": "https://acme.com",
        "license_url": "http://docs.osparc.io/#/docs/support/license"
      }
      */
      return this.__getFromStaticInfo("vendor", null);
    },

    getManuals: function() {
      /*
      [{
        "label": "main",
        "url": "doc.acme.com"
      }]
      */
      return this.__getFromStaticInfo("manuals", []);
    },

    getIssues: function() {
      /*
      [{
        "label": "github",
        "login_url": "https://github.com/ITISFoundation/osparc-simcore",
        "new_url": "https://github.com/ITISFoundation/osparc-simcore/issues/new/choose"
      }]
      */
      return this.__getFromStaticInfo("issues", []);
    },

    getSupports: function() {
      /*
      [{
        "kind": "forum", // "web", "email", "forum"
        "label": "forum",
        "url": "forum.acme.com"
      }]
      */
      return this.__getFromStaticInfo("support", []);
    }
  }
});
