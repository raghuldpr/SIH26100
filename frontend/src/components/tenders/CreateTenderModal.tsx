import React, { useState } from "react";
import { Button, Input, Modal, Select } from "../ui";
import { createTender } from "../../api/tenders";
import { TenderCreate, TenderStatus } from "../../types";
import { Plus, AlertCircle, FileText } from "lucide-react";
import { ApiClientError } from "../../api/client";

export interface CreateTenderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTenderCreated: (tender: any) => void;
}

export const CreateTenderModal: React.FC<CreateTenderModalProps> = ({
  isOpen,
  onClose,
  onTenderCreated,
}) => {
  const [tenderNumber, setTenderNumber] = useState("");
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [department, setDepartment] = useState("General");
  const [category, setCategory] = useState("Works");
  const [description, setDescription] = useState("");
  const [bidStartDate, setBidStartDate] = useState("");
  const [bidEndDate, setBidEndDate] = useState("");
  const [status, setStatus] = useState<TenderStatus>("DRAFT");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const resetForm = () => {
    setTenderNumber("");
    setTitle("");
    setOrganization("");
    setDepartment("General");
    setCategory("Works");
    setDescription("");
    setBidStartDate("");
    setBidEndDate("");
    setStatus("DRAFT");
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!tenderNumber.trim() || !title.trim() || !organization.trim()) {
      setErrorMessage("Tender reference number, title, and organization are required.");
      return;
    }

    if (bidStartDate && bidEndDate && new Date(bidEndDate) < new Date(bidStartDate)) {
      setErrorMessage("Bid deadline cannot be earlier than submission start date.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: TenderCreate = {
        tender_number: tenderNumber.trim(),
        title: title.trim(),
        organization: organization.trim(),
        department: department.trim() || "General",
        category: category.trim() || "Works",
        description: description.trim() || undefined,
        bid_start_date: bidStartDate ? new Date(bidStartDate).toISOString() : undefined,
        bid_end_date: bidEndDate ? new Date(bidEndDate).toISOString() : undefined,
        status,
      };

      const newTender = await createTender(payload);
      resetForm();
      onTenderCreated(newTender);
      onClose();
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(err?.message || "Failed to create tender notice.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="2xl"
      title={
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          <span>Register New GeM Procurement Tender</span>
        </div>
      }
      description="Create a tender notice record to begin document intake and clause extraction."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            isLoading={isSubmitting}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Create Tender Notice
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMessage && (
          <div className="p-3.5 rounded-lg bg-error-container text-error text-xs flex items-start gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span className="font-medium">{errorMessage}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Tender Reference Number *"
            placeholder="e.g. GEM/2026/B/879201"
            value={tenderNumber}
            onChange={(e) => setTenderNumber(e.target.value)}
            required
            disabled={isSubmitting}
          />

          <Input
            label="Procuring Organization *"
            placeholder="e.g. Bharat Sanchar Nigam Limited"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
            required
            disabled={isSubmitting}
          />
        </div>

        <Input
          label="Tender Title *"
          placeholder="e.g. Supply and Installation of Optical Fiber Infrastructure"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          disabled={isSubmitting}
        />

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input
            label="Department / Division"
            placeholder="e.g. Telecommunications"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            disabled={isSubmitting}
          />

          <Select
            label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={[
              { value: "Works", label: "Civil & Engineering Works" },
              { value: "Goods", label: "Goods & Equipment Supply" },
              { value: "Services", label: "Consulting & Services" },
              { value: "IT", label: "Information Technology" },
            ]}
            disabled={isSubmitting}
          />

          <Select
            label="Initial Status"
            value={status}
            onChange={(e) => setStatus(e.target.value as TenderStatus)}
            options={[
              { value: "DRAFT", label: "Draft Preparation" },
              { value: "OPEN", label: "Open for Bidding" },
              { value: "PUBLISHED", label: "Published on GeM" },
            ]}
            disabled={isSubmitting}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Submission Start Date"
            type="datetime-local"
            value={bidStartDate}
            onChange={(e) => setBidStartDate(e.target.value)}
            disabled={isSubmitting}
          />

          <Input
            label="Submission Deadline"
            type="datetime-local"
            value={bidEndDate}
            onChange={(e) => setBidEndDate(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-on-surface uppercase tracking-wider">
            Scope / Description
          </label>
          <textarea
            rows={3}
            placeholder="Detailed tender scope, mandatory qualifications, and technical instructions..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isSubmitting}
            className="flex w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest p-3 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all custom-scrollbar"
          />
        </div>
      </form>
    </Modal>
  );
};
