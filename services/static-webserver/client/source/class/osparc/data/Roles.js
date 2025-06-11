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


qx.Class.define("osparc.data.Roles", {
  type: "static",

  statics: {
    ORG: {
      "noRead": {
        id: "noRead",
        label: qx.locale.Manager.tr("Restricted Member"),
        longLabel: qx.locale.Manager.tr("Restricted member: no Read access"),
        canDo: [
          qx.locale.Manager.tr("- Can access content shared within the Organization")
        ],
        accessRights: {
          "read": false,
          "write": false,
          "delete": false
        },
      },
      "read": {
        id: "read",
        label: qx.locale.Manager.tr("Member"),
        longLabel: qx.locale.Manager.tr("Member: Read access"),
        canDo: [
          qx.locale.Manager.tr("- Can see other members"),
          qx.locale.Manager.tr("- Can share with other members")
        ],
        accessRights: {
          "read": true,
          "write": false,
          "delete": false
        },
      },
      "write": {
        id: "write",
        label: qx.locale.Manager.tr("Manager"),
        longLabel: qx.locale.Manager.tr("Manager: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- Can Add/Delete members"),
          qx.locale.Manager.tr("- Can Promote/Demote members"),
          qx.locale.Manager.tr("- Can Edit Organization details")
        ],
        accessRights: {
          "read": true,
          "write": true,
          "delete": false
        },
      },
      "delete": {
        id: "delete",
        label: qx.locale.Manager.tr("Administrator"),
        longLabel: qx.locale.Manager.tr("Admin: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- Can Delete the Organization")
        ],
        accessRights: {
          "read": true,
          "write": true,
          "delete": true
        },
      }
    },
    // study & templates
    STUDY: {
      "read": {
        id: "read",
        label: qx.locale.Manager.tr("User"),
        longLabel: qx.locale.Manager.tr("User: Read access"),
        canDo: [
          qx.locale.Manager.tr("- Can open it without making changes")
        ],
        accessRights: {
          "read": true,
          "write": false,
          "delete": false
        },
      },
      "write": {
        id: "write",
        label: qx.locale.Manager.tr("Editor"),
        longLabel: qx.locale.Manager.tr("Editor: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- Can make changes"),
          qx.locale.Manager.tr("- Can share it")
        ],
        accessRights: {
          "read": true,
          "write": true,
          "delete": false
        },
      },
      "delete": {
        id: "delete",
        label: qx.locale.Manager.tr("Owner"),
        longLabel: qx.locale.Manager.tr("Owner: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- Can delete it")
        ],
        accessRights: {
          "read": true,
          "write": true,
          "delete": true
        },
      }
    },
    SERVICES: {
      "read": {
        id: "read",
        label: qx.locale.Manager.tr("User"),
        longLabel: qx.locale.Manager.tr("User: Read access"),
        canDo: [
          qx.locale.Manager.tr("- Can use it")
        ],
        accessRights: {
          "execute": true,
          "write": false
        },
      },
      "write": {
        id: "write",
        label: qx.locale.Manager.tr("Editor"),
        longLabel: qx.locale.Manager.tr("Editor: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- Can make changes"),
          qx.locale.Manager.tr("- Can share it")
        ],
        accessRights: {
          "execute": true,
          "write": true
        },
      },
    },
    WALLET: {
      "read": {
        id: "read",
        label: qx.locale.Manager.tr("User"),
        longLabel: qx.locale.Manager.tr("User: Read access"),
        canDo: [
          qx.locale.Manager.tr("- Can use the credits")
        ],
        accessRights: {
          "read": true,
          "write": false,
          "delete": false
        },
      },
      "write": {
        id: "write",
        label: qx.locale.Manager.tr("Accountant"),
        longLabel: qx.locale.Manager.tr("Accountant: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- Can Add/Delete members"),
          qx.locale.Manager.tr("- Can Edit Credit Account details")
        ],
        accessRights: {
          "read": true,
          "write": true,
          "delete": false
        },
      }
    },
    WORKSPACE: {
      "read": {
        id: "read",
        label: qx.locale.Manager.tr("Viewer"),
        longLabel: qx.locale.Manager.tr("Viewer: Read access"),
        canDo: [
          qx.locale.Manager.tr("- Can inspect the content and open ") + osparc.product.Utils.getStudyAlias({plural: true}) + qx.locale.Manager.tr(" without making changes")
        ]
      },
      "write": {
        id: "write",
        label: qx.locale.Manager.tr("Editor"),
        longLabel: qx.locale.Manager.tr("Editor: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- Can add ") + osparc.product.Utils.getStudyAlias({plural: true}),
          qx.locale.Manager.tr("- Can add folders"),
        ]
      },
      "delete": {
        id: "delete",
        label: qx.locale.Manager.tr("Owner"),
        longLabel: qx.locale.Manager.tr("Owner: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- Can rename workspace"),
          qx.locale.Manager.tr("- Can share it"),
          qx.locale.Manager.tr("- Can delete it")
        ]
      }
    },

    __createRolesLayout: function(roles, showWording = true) {
      const rolesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
        alignY: "middle",
        paddingRight: 10
      });
      rolesLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      if (showWording) {
        const rolesText = new qx.ui.basic.Label(qx.locale.Manager.tr("Roles")).set({
          alignY: "middle",
          font: "text-13"
        });
        rolesLayout.add(rolesText);
      }

      let text = "";
      const values = Object.values(roles);
      values.forEach((role, idx) => {
        text += role.longLabel + ":<br>";
        role.canDo.forEach(can => {
          text += can + "<br>";
        });
        if (idx !== values.length-1) {
          text += "<br>";
        }
      });
      const infoHint = new osparc.ui.hint.InfoHint(text).set({
        alignY: "middle"
      });
      rolesLayout.add(infoHint);

      return rolesLayout;
    },

    createRolesOrgInfo: function() {
      return this.__createRolesLayout(osparc.data.Roles.ORG);
    },

    createRolesWalletInfo: function() {
      return this.__createRolesLayout(osparc.data.Roles.WALLET);
    },

    createRolesStudyInfo: function() {
      return this.__createRolesLayout(osparc.data.Roles.STUDY);
    },

    createRolesServicesInfo: function() {
      return this.__createRolesLayout(osparc.data.Roles.SERVICES);
    },

    createRolesWorkspaceInfo: function(showWording = true) {
      return this.__createRolesLayout(osparc.data.Roles.WORKSPACE, showWording);
    },

    replaceSpacerWithWidget: function(rolesLayout, widget) {
      if (rolesLayout && rolesLayout.getChildren()) {
        // remove spacer
        rolesLayout.remove(rolesLayout.getChildren()[0]);
        // add widget
        rolesLayout.addAt(widget, 0, {
          flex: 1
        });
      }
    },
  }
});
