-- Supabase SQL schema for the patients table used by the Vapi webhook.
-- Run this in the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS public.patients (
    patient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name TEXT NOT NULL CHECK (char_length(trim(first_name)) BETWEEN 1 AND 50),
    last_name TEXT NOT NULL CHECK (char_length(trim(last_name)) BETWEEN 1 AND 50),
    date_of_birth DATE NOT NULL CHECK (date_of_birth <= CURRENT_DATE),
    sex TEXT NOT NULL CHECK (sex IN ('Male', 'Female', 'Other', 'Decline to Answer')),
    phone_number TEXT NOT NULL CHECK (phone_number ~ '^[0-9]{10}$'),
    email TEXT NULL CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'),
    address_line_1 TEXT NOT NULL CHECK (char_length(trim(address_line_1)) > 0),
    address_line_2 TEXT NULL,
    city TEXT NOT NULL CHECK (char_length(trim(city)) BETWEEN 1 AND 100),
    state TEXT NOT NULL CHECK (state ~ '^[A-Z]{2}$'),
    zip_code TEXT NOT NULL CHECK (zip_code ~ '^[0-9]{5}(-[0-9]{4})?$'),
    insurance_provider TEXT NULL,
    insurance_member_id TEXT NULL,
    preferred_language TEXT NOT NULL DEFAULT 'English',
    emergency_contact_name TEXT NULL,
    emergency_contact_phone TEXT NULL CHECK (emergency_contact_phone IS NULL OR emergency_contact_phone ~ '^[0-9]{10}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_patients_phone_number ON public.patients (phone_number);
CREATE INDEX IF NOT EXISTS idx_patients_deleted_at ON public.patients (deleted_at);

-- Optional: soft-delete-friendly trigger to keep updated_at fresh on updates.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_patients_updated_at ON public.patients;
CREATE TRIGGER trg_patients_updated_at
BEFORE UPDATE ON public.patients
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
