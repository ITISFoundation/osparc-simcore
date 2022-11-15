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
      return new Promise(resolve => {
        osparc.store.StaticInfo.getInstance().getValue(key)
          .then(issuesData => {
            issuesData ? resolve(issuesData) : resolve(defaultValue);
          })
          .catch(() => resolve(defaultValue));
      });
    },

    getDisplayName: function() {
      return this.__getFromStaticInfo("displayName", "o\u00b2S\u00b2PARC");
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

    getManuals: function() {
      /*
      [{
        "label": "main",
        "url": "doc.acme.com"
      }]
      */
      return this.__getFromStaticInfo("manuals", []);
    },

    getSupports: function() {
      /*
      [{
        "kind": "forum",
        "label": "forum",
        "url": "forum.acme.com"
      }]
      */
      return this.__getFromStaticInfo("support", []);
    }
  }
});
