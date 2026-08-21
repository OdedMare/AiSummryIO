"use client";

import { CheckCircle2, Save } from "lucide-react";
import type { PackageVersion } from "@/types";
import {
  PackageFields,
  PackageFormHeader,
  PackageList,
} from "./packages/PackageFields";
import {
  AdvancedPackageFields,
  FieldPalette,
  PackageInspector,
} from "./packages/PackageSchema";
import {
  dropJsonField,
  dropTextField,
} from "./packages/packageModel";
import { usePackageCatalog } from "./packages/usePackageCatalog";

export default function PackageCatalog({
  projectId, items,
  onRefresh,
}: {
  projectId: string;
  items: PackageVersion[];
  onRefresh: () => Promise<void>;
}) {
  const catalog = usePackageCatalog(projectId, onRefresh);
  return (
    <div className="studio-split">
      <PackageList items={items} onEdit={catalog.edit}
        onNew={catalog.startNew}
        onRemove={catalog.remove} />
      <form className="studio-form" onSubmit={catalog.save}>
        <PackageFormHeader projectId={projectId} form={catalog.form}
          editing={!!catalog.editingId}
          inspection={catalog.inspection} onApply={catalog.applyDraft} />
        <PackageFields projectId={projectId} form={catalog.form} update={catalog.update}
          onDropField={(event, target) =>
            dropTextField(event, target, catalog.setForm)}
          inspection={catalog.inspection}
          onApplyField={catalog.applyField} />
        <PackageInspector form={catalog.form}
          inspectId={catalog.inspectId} setInspectId={catalog.setInspectId}
          inspecting={catalog.inspecting} inspect={catalog.inspect}
          inspection={catalog.inspection} />
        <FieldPalette form={catalog.form} update={catalog.update}
          target={catalog.fieldTarget} setTarget={catalog.setFieldTarget}
          onInsert={catalog.insert} />
        <AdvancedPackageFields form={catalog.form} update={catalog.update}
          onDropField={(event, target) => dropJsonField(
            event,
            target,
            catalog.inspection,
            catalog.setForm,
          )} />
        {catalog.error
          && <p className="form-error" role="alert">{catalog.error}</p>}
        {catalog.message && <p className="form-success">
          <CheckCircle2 size={16} /> {catalog.message}
        </p>}
        <div className="form-actions">
          {catalog.editingId
            && <button type="button" className="secondary-button"
              onClick={catalog.reset}>ביטול עריכה</button>}
          <button className="primary-button" type="submit"
            disabled={catalog.saving}>
            <Save size={17} /> {catalog.saving ? "שומר…"
              : catalog.editingId ? "שמירת שינויים" : "שמירת טול"}
          </button>
        </div>
      </form>
    </div>
  );
}
