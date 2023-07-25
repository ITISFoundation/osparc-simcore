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
      0: {
        id: "noRead",
        label: qx.locale.Manager.tr("User"),
        longLabel: qx.locale.Manager.tr("User: no Read access"),
        canDo: [
          qx.locale.Manager.tr("- can access content shared within the Organization")
        ]
      },
      1: {
        id: "read",
        label: qx.locale.Manager.tr("Member"),
        longLabel: qx.locale.Manager.tr("Member: Read access"),
        canDo: [
          qx.locale.Manager.tr("- can See other members"),
          qx.locale.Manager.tr("- can Share with other members")
        ]
      },
      2: {
        id: "write",
        label: qx.locale.Manager.tr("Manager"),
        longLabel: qx.locale.Manager.tr("Manager: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- can Add/Delete members"),
          qx.locale.Manager.tr("- can Promote/Demote members"),
          qx.locale.Manager.tr("- can Edit Organization details")
        ]
      },
      3: {
        id: "delete",
        label: qx.locale.Manager.tr("Administrator"),
        longLabel: qx.locale.Manager.tr("Admin: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- can Delete the Organization")
        ]
      }
    },

    RESOURCE: {
      1: {
        id: "read",
        label: qx.locale.Manager.tr("Viewer"),
        longLabel: qx.locale.Manager.tr("Viewer: Read access"),
        canDo: [
          qx.locale.Manager.tr("- can open it")
        ]
      },
      2: {
        id: "write",
        label: qx.locale.Manager.tr("Collaborator"),
        longLabel: qx.locale.Manager.tr("Collaborator: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- can make changes")
        ]
      },
      3: {
        id: "delete",
        label: qx.locale.Manager.tr("Owner"),
        longLabel: qx.locale.Manager.tr("Owner: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- can delete it")
        ]
      }
    },

    WALLET: {
      0: {
        id: "noRead",
        label: qx.locale.Manager.tr("No Read"),
        longLabel: qx.locale.Manager.tr("No Read: no Read access"),
        canDo: [
          qx.locale.Manager.tr("- something went wrong")
        ]
      },
      1: {
        id: "read",
        label: qx.locale.Manager.tr("User"),
        longLabel: qx.locale.Manager.tr("User: Read access"),
        canDo: [
          qx.locale.Manager.tr("- can use the credits")
        ]
      },
      2: {
        id: "write",
        label: qx.locale.Manager.tr("Accountant"),
        longLabel: qx.locale.Manager.tr("Accountant: Read/Write access"),
        canDo: [
          qx.locale.Manager.tr("- can Add/Delete members"),
          qx.locale.Manager.tr("- can Edit Wallet details")
        ]
      },
      3: {
        id: "delete",
        label: qx.locale.Manager.tr("Administrator"),
        longLabel: qx.locale.Manager.tr("Admin: Read/Write/Delete access"),
        canDo: [
          qx.locale.Manager.tr("- can Delete the Wallet")
        ]
      }
    },

    __createIntoFromRoles: function(roles) {
      const rolesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
        alignY: "middle",
        paddingRight: 10
      });
      rolesLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const rolesText = new qx.ui.basic.Label(qx.locale.Manager.tr("Roles")).set({
        font: "text-13"
      });
      rolesLayout.add(rolesText);
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
      const infoHint = new osparc.ui.hint.InfoHint(text);
      rolesLayout.add(infoHint);
      return rolesLayout;
    },

    createRolesOrgInfo: function() {
      return this.__createIntoFromRoles(osparc.data.Roles.ORG);
    },

    createRolesResourceInfo: function() {
      return this.__createIntoFromRoles(osparc.data.Roles.RESOURCE);
    }
  }
});
