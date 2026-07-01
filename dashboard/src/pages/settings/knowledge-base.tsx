import { useState, useRef } from "react";
import { ScriptEditor } from "@/components/editors/ScriptEditor";
import { RagConfigPanel } from "@/components/editors/RagConfigPanel";
import { useFaqEntries, useKnowledgeDocuments } from "@/hooks/use-settings";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn, formatFileSize } from "@/lib/utils";
import { Upload, FileText, Trash2, RefreshCw, Plus, X, Check } from "lucide-react";

const statusColors: Record<string, string> = {
  uploading: "bg-amber-100 text-amber-700",
  processing: "bg-blue-100 text-blue-700",
  indexed: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
};

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState("documents");
  const { data: documents, isLoading: docsLoading } = useKnowledgeDocuments();
  const { data: faqs, isLoading: faqsLoading } = useFaqEntries();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [newFaq, setNewFaq] = useState({ question: "", answer: "" });
  const [showNewFaq, setShowNewFaq] = useState(false);
  const [ragChunk, setRagChunk] = useState(512);
  const [ragTopK, setRagTopK] = useState(4);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Knowledge Base" description="Documents and FAQs your receptionist can use" />

      <RagConfigPanel
        chunkSize={ragChunk}
        topK={ragTopK}
        onChunkSize={setRagChunk}
        onTopK={setRagTopK}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="faqs">FAQs</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="space-y-4">
          {/* Upload Area */}
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors",
              isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:bg-accent"
            )}
          >
            <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">Drop files here or click to upload</p>
            <p className="text-xs text-muted-foreground">PDF, CSV, TXT, DOCX, MD up to 10MB</p>
            <input ref={fileInputRef} type="file" multiple accept=".pdf,.csv,.txt,.docx,.md" className="hidden" />
          </div>

          {/* Document List */}
          {docsLoading ? <LoadingSpinner /> : documents && documents.length > 0 ? (
            <div className="rounded-lg border">
              <div className="grid grid-cols-12 gap-4 border-b p-3 text-xs font-semibold uppercase text-muted-foreground">
                <div className="col-span-4">Name</div>
                <div className="col-span-2">Type</div>
                <div className="col-span-2">Size</div>
                <div className="col-span-2">Status</div>
                <div className="col-span-2">Actions</div>
              </div>
              {documents.map((doc) => (
                <div key={doc.id} className="grid grid-cols-12 gap-4 border-b p-3 items-center last:border-0">
                  <div className="col-span-4 flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm truncate">{doc.originalName}</span>
                  </div>
                  <div className="col-span-2 text-sm uppercase">{doc.fileType}</div>
                  <div className="col-span-2 text-sm text-muted-foreground">{formatFileSize(doc.fileSize)}</div>
                  <div className="col-span-2">
                    <Badge className={statusColors[doc.status]}>{doc.status}</Badge>
                  </div>
                  <div className="col-span-2 flex gap-1">
                    <Button variant="ghost" size="sm"><RefreshCw className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="sm"><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No documents" description="Upload documents for your receptionist to reference." illustration="default" />
          )}
        </TabsContent>

        <TabsContent value="faqs" className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setShowNewFaq(true)}>
              <Plus className="mr-1 h-4 w-4" /> Add FAQ
            </Button>
          </div>

          {showNewFaq && (
            <div className="rounded-lg border bg-card p-4 space-y-3">
              <Input
                placeholder="Question"
                value={newFaq.question}
                onChange={(e) => setNewFaq((f) => ({ ...f, question: e.target.value }))}
              />
              <ScriptEditor
                storageKey="kb-faq-draft"
                label="Answer"
                placeholder="Write the answer callers should hear..."
                value={newFaq.answer}
                onChange={(answer) => setNewFaq((f) => ({ ...f, answer }))}
                rows={4}
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={() => { setShowNewFaq(false); setNewFaq({ question: "", answer: "" }); }}>
                  <Check className="mr-1 h-4 w-4" /> Save
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setShowNewFaq(false)}>
                  <X className="mr-1 h-4 w-4" /> Cancel
                </Button>
              </div>
            </div>
          )}

          {faqsLoading ? <LoadingSpinner /> : faqs && faqs.length > 0 ? (
            <div className="space-y-2">
              {faqs.map((faq) => (
                <div key={faq.id} className="rounded-lg border bg-card p-4">
                  <p className="font-medium">{faq.question}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{faq.answer}</p>
                  {faq.category && <Badge variant="secondary" className="mt-2">{faq.category}</Badge>}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No FAQs" description="Add frequently asked questions to improve caller answers." illustration="search" />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
