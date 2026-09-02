import React, { useState } from "react";
import { Button, Input, Modal, Select } from "../ui";
import { createBidder } from "../../api/bidders";
import { BidderCreate, BidderStatus } from "../../types";
import { Building2, Plus, AlertCircle } from "lucide-react";
import { ApiClientError } from "../../api/client";

export interface CreateBidderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBidderCreated: (bidder: any) => void;
}

export const CreateBidderModal: React.FC<CreateBidderModalProps> = ({
  isOpen,
  onClose,
  onBidderCreated,
}) => {
  const [companyName, setCompanyName] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [gstNumber, setGstNumber] = useState("");
  const [panNumber, setPanNumber] = useState("");
  const [udyamNumber, setUdyamNumber] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [status, setStatus] = useState<BidderStatus>("ACTIVE");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const resetForm = () => {
    setCompanyName("");
    setRegistrationNumber("");
    setGstNumber("");
    setPanNumber("");
    setUdyamNumber("");
    setContactPerson("");
    setEmail("");
    setPhone("");
    setAddress("");
    setStatus("ACTIVE");
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!companyName.trim()) {
      setErrorMessage("Company / organization name is required.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: BidderCreate = {
        company_name: companyName.trim(),
        registration_number: registrationNumber.trim() || undefined,
        gst_number: gstNumber.trim().toUpperCase() || undefined,
        pan_number: panNumber.trim().toUpperCase() || undefined,
        udyam_number: udyamNumber.trim().toUpperCase() || undefined,
        contact_person: contactPerson.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        address: address.trim() || undefined,
        status,
      };

      const newBidder = await createBidder(payload);
      resetForm();
      onBidderCreated(newBidder);
      onClose();
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(err?.message || "Failed to register bidder entity.");
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
          <Building2 className="h-5 w-5 text-primary" />
          <span>Register New Bidder Organization</span>
        </div>
      }
      description="Create a reusable bidder profile for procurement participation and verification."
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
            Register Bidder
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

        <Input
          label="Company / Organization Name *"
          placeholder="e.g. Apex Teleinfra Private Limited"
          value={companyName}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCompanyName(e.target.value)}
          required
          disabled={isSubmitting}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="GSTIN Number"
            placeholder="e.g. 07AAAAA0000A1Z5"
            value={gstNumber}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGstNumber(e.target.value)}
            disabled={isSubmitting}
          />

          <Input
            label="PAN Number"
            placeholder="e.g. AAAAA0000A"
            value={panNumber}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPanNumber(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Corporate Registration / CIN"
            placeholder="e.g. U72900DL2020PTC123456"
            value={registrationNumber}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRegistrationNumber(e.target.value)}
            disabled={isSubmitting}
          />

          <Input
            label="MSME Udyam Number"
            placeholder="e.g. UDYAM-DL-01-0012345"
            value={udyamNumber}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUdyamNumber(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input
            label="Contact Person"
            placeholder="e.g. Rahul Sharma"
            value={contactPerson}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setContactPerson(e.target.value)}
            disabled={isSubmitting}
          />

          <Input
            label="Official Email"
            type="email"
            placeholder="e.g. contact@apexteleinfra.com"
            value={email}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
            disabled={isSubmitting}
          />

          <Input
            label="Phone / Mobile"
            placeholder="e.g. +91 98765 43210"
            value={phone}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPhone(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-on-surface uppercase tracking-wider">
            Registered Office Address
          </label>
          <textarea
            rows={2}
            placeholder="Full postal address of registered corporate office..."
            value={address}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setAddress(e.target.value)}
            disabled={isSubmitting}
            className="flex w-full rounded-lg border border-outline-variant/60 bg-surface-container-lowest p-3 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all custom-scrollbar"
          />
        </div>

        <div>
          <Select
            label="Initial Eligibility Status"
            value={status}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatus(e.target.value as BidderStatus)}
            options={[
              { value: "ACTIVE", label: "Active / Eligible" },
              { value: "INACTIVE", label: "Inactive" },
              { value: "SUSPENDED", label: "Suspended" },
            ]}
            disabled={isSubmitting}
          />
        </div>
      </form>
    </Modal>
  );
};
