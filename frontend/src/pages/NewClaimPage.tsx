import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { Upload, Car, AlertCircle, PlusCircle } from "lucide-react";

interface Vehicle {
  id: string;
  registration_number: string;
  make: string;
  model: string;
  year: number;
}

export default function NewClaimPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1: vehicle, 2: details, 3: upload
  const [vehicleId, setVehicleId] = useState("");
  const [description, setDescription] = useState("");
  const [incidentDate, setIncidentDate] = useState("");
  const [incidentLocation, setIncidentLocation] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [claimId, setClaimId] = useState("");

  // New vehicle form (shown when adding a new vehicle)
  const [showNewVehicle, setShowNewVehicle] = useState(false);
  const [regNumber, setRegNumber] = useState("");
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("2022");

  // Fetch existing vehicles
  const { data: vehicles, refetch: refetchVehicles } = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => api.get<Vehicle[]>("/vehicles").then((r) => r.data),
  });

  // If user has no vehicles, show the form directly
  useEffect(() => {
    if (vehicles && vehicles.length === 0) {
      setShowNewVehicle(true);
    }
  }, [vehicles]);

  const handleSelectVehicle = (id: string) => {
    setVehicleId(id);
    setStep(2);
  };

  const handleRegisterVehicle = async () => {
    setError("");
    try {
      const res = await api.post("/vehicles", {
        registration_number: regNumber,
        make,
        model,
        year: parseInt(year),
      });
      setVehicleId(res.data.id);
      refetchVehicles();
      setShowNewVehicle(false);
      setStep(2);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || "Failed to register vehicle");
    }
  };

  const handleCreateClaim = async () => {
    setError("");
    try {
      const res = await api.post("/claims", {
        vehicle_id: vehicleId,
        description,
        incident_date: incidentDate || undefined,
        incident_location: incidentLocation || undefined,
      });
      setClaimId(res.data.id);
      setStep(3);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || "Failed to create claim");
    }
  };

  const handleUploadAndSubmit = async () => {
    if (!files.length) {
      setError("Please upload at least one image");
      return;
    }

    setLoading(true);
    setError("");

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        await api.post(`/claims/${claimId}/images`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      }
      await api.post(`/claims/${claimId}/submit`);
      navigate(`/claims/${claimId}`);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || "Failed to upload images");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">File New Claim</h1>

      {/* Progress steps */}
      <div className="flex items-center gap-2 mb-8">
        {["Vehicle", "Details", "Photos"].map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                i + 1 <= step
                  ? "bg-primary-600 text-white"
                  : "bg-gray-200 text-gray-500"
              }`}
            >
              {i + 1}
            </div>
            <span className={`text-xs ${i + 1 <= step ? "text-primary-600" : "text-gray-400"}`}>
              {label}
            </span>
            {i < 2 && <div className="w-8 h-0.5 bg-gray-200" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Step 1: Vehicle Selection */}
      {step === 1 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Car className="w-5 h-5 text-primary-600" />
              <h2 className="text-lg font-semibold">Select Vehicle</h2>
            </div>
            {!showNewVehicle && vehicles && vehicles.length > 0 && (
              <button
                onClick={() => setShowNewVehicle(true)}
                className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-700"
              >
                <PlusCircle className="w-4 h-4" />
                Add New
              </button>
            )}
          </div>

          {/* Existing vehicles list */}
          {!showNewVehicle && vehicles && vehicles.length > 0 && (
            <div className="space-y-2">
              {vehicles.map((v) => (
                <button
                  key={v.id}
                  onClick={() => handleSelectVehicle(v.id)}
                  className="w-full text-left p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
                >
                  <p className="font-medium text-gray-900">
                    {v.make} {v.model} ({v.year})
                  </p>
                  <p className="text-sm text-gray-500">{v.registration_number}</p>
                </button>
              ))}
            </div>
          )}

          {/* New vehicle form */}
          {showNewVehicle && (
            <div className="space-y-3 pt-2 border-t border-gray-100">
              <p className="text-sm text-gray-500">Register a new vehicle</p>
              <input
                placeholder="Registration Number (e.g., MH02AB1234)"
                value={regNumber}
                onChange={(e) => setRegNumber(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  placeholder="Make (e.g., Hyundai)"
                  value={make}
                  onChange={(e) => setMake(e.target.value)}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <input
                  placeholder="Model (e.g., Creta)"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              <input
                placeholder="Year"
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              <div className="flex gap-2">
                {vehicles && vehicles.length > 0 && (
                  <button
                    onClick={() => setShowNewVehicle(false)}
                    className="flex-1 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                )}
                <button
                  onClick={handleRegisterVehicle}
                  className="flex-1 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                >
                  Register & Continue
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Incident Details */}
      {step === 2 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold">Incident Details</h2>
          <textarea
            placeholder="Describe what happened (e.g., hit a divider on the highway)..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-500 mb-1">Incident Date</label>
              <input
                type="date"
                value={incidentDate}
                onChange={(e) => setIncidentDate(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Location</label>
              <input
                placeholder="e.g., Mumbai, Western Express Highway"
                value={incidentLocation}
                onChange={(e) => setIncidentLocation(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
          </div>
          <button
            onClick={handleCreateClaim}
            className="w-full py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            Continue
          </button>
        </div>
      )}

      {/* Step 3: Upload Images */}
      {step === 3 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Upload className="w-5 h-5 text-primary-600" />
            <h2 className="text-lg font-semibold">Upload Damage Photos</h2>
          </div>
          <p className="text-sm text-gray-500">
            Upload clear photos of the damage from multiple angles. Better photos = better assessment.
          </p>

          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-primary-300 transition-colors">
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600">Click to upload or drag and drop</p>
              <p className="text-xs text-gray-400 mt-1">PNG, JPG up to 10MB each</p>
            </label>
          </div>

          {files.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {files.map((f, i) => (
                <div
                  key={i}
                  className="px-3 py-1 bg-primary-50 text-primary-700 text-sm rounded-full"
                >
                  {f.name}
                </div>
              ))}
            </div>
          )}

          <button
            onClick={handleUploadAndSubmit}
            disabled={loading || !files.length}
            className="w-full py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? "Uploading & Processing..." : "Submit Claim for AI Assessment"}
          </button>
        </div>
      )}
    </div>
  );
}
